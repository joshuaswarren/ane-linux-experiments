/* Data-driven CSNE command sequencer (legacy transport).
 *
 * Runs apple/ane/seq/00.bin, 01.bin, ... in order after CONFIG_GET,
 * stopping at the first missing file or failed step. Each file names
 * one command, the DMA buffers it needs, and the address patches that
 * bind them, so a new command layout is a file edit, not a rebuild.
 * Writing anything to /sys/kernel/debug/ane_t6021_seq/run continues at
 * the next unused index, so later steps can be staged without a reboot.
 *
 * File layout (little-endian):
 *   struct seq_hdr
 *   struct seq_buf    [nbufs]
 *   struct seq_patch  [npatch]
 *   u8 command        [cmd_len]
 *   u8 fill           [sum of seq_buf.fill_len, in buffer order]
 *
 * Buffers, the command, and the step table stay allocated until reboot,
 * like every other legacy allocation, so the firmware never sees a freed
 * address. */

#define ANE_SEQ_MAGIC		0x51454e41	/* "ANEQ" */
#define ANE_SEQ_STEPS		64
#define ANE_SEQ_BUFS		16
#define ANE_SEQ_REPLY		SZ_4K
#define ANE_SEQ_DUMP_MAX	SZ_4K

enum ane_seq_patch_kind {
	ANE_SEQ_DMA = 1,	/* u64 dma(buf[src]) + src_off */
	ANE_SEQ_REPLY32 = 2,	/* u32 reply[step src] at src_off */
	ANE_SEQ_STEP_DMA = 3,	/* u64 dma(step src>>8, buf src&0xff) + src_off */
};

struct ane_seq_hdr {
	__le32 magic;
	__le16 opcode;
	__le16 channel;
	__le32 cmd_len;
	__le32 nbufs;
	__le32 npatch;
	__le32 timeout_ms;
	__le32 dump_reply;
	__le32 settle_ms;	/* wait before dumping buffers */
};

struct ane_seq_buf {
	__le32 size;
	__le32 fill_len;
	__le32 dump_len;
	__le32 rsvd;
};

struct ane_seq_patch {
	__le16 kind;
	__le16 dst_buf;		/* 0xffff = the command */
	__le32 dst_off;
	__le32 src;
	__le32 src_off;
};

static_assert(sizeof(struct ane_seq_hdr) == 32);
static_assert(sizeof(struct ane_seq_buf) == 16);
static_assert(sizeof(struct ane_seq_patch) == 16);

struct ane_seq_step {
	struct ane_legacy_buffer *buf[ANE_SEQ_BUFS];
	u32 nbufs;
	u8 reply[ANE_SEQ_REPLY];
	u32 reply_len;
};

static int ane_seq_patch_one(struct ane_rtclient *ane, struct ane_seq_step *steps,
			     unsigned int cur, struct ane_legacy_buffer *command,
			     const struct ane_seq_patch *p)
{
	struct ane_seq_step *s = &steps[cur];
	u32 dst_buf = le16_to_cpu(p->dst_buf), dst_off = le32_to_cpu(p->dst_off);
	u32 src = le32_to_cpu(p->src), src_off = le32_to_cpu(p->src_off);
	struct ane_legacy_buffer *dst;
	u64 value;
	size_t width;

	if (dst_buf == 0xffff)
		dst = command;
	else if (dst_buf < s->nbufs)
		dst = s->buf[dst_buf];
	else
		return -EINVAL;

	switch (le16_to_cpu(p->kind)) {
	case ANE_SEQ_DMA:
		if (src >= s->nbufs)
			return -EINVAL;
		value = s->buf[src]->dma + src_off;
		width = 8;
		break;
	case ANE_SEQ_REPLY32:
		if (src >= cur || src_off > steps[src].reply_len - 4)
			return -EINVAL;
		value = get_unaligned_le32(steps[src].reply + src_off);
		width = 4;
		break;
	case ANE_SEQ_STEP_DMA:
		if ((src >> 8) >= cur || (src & 0xff) >= steps[src >> 8].nbufs)
			return -EINVAL;
		value = steps[src >> 8].buf[src & 0xff]->dma + src_off;
		width = 8;
		break;
	default:
		return -EINVAL;
	}
	if (dst_off > dst->size - width)
		return -EINVAL;
	if (width == 8)
		put_unaligned_le64(value, (u8 *)dst->cpu + dst_off);
	else
		put_unaligned_le32(value, (u8 *)dst->cpu + dst_off);
	dev_info(ane->dev, "SEQ %u patch kind=%u dst=%#x+%#x value=%#llx\n", cur,
		 le16_to_cpu(p->kind), dst_buf, dst_off, value);
	return 0;
}

/* Every dumped buffer is also published whole as a read-only debugfs
 * blob, /sys/kernel/debug/ane_t6021_seq/sNNbMM, so userspace can check
 * outputs too large for the kernel log. The DMA memory is held until
 * reboot, so the blob never outlives its backing store. */
static struct dentry *ane_seq_dbg;

static void ane_seq_blob(struct ane_rtclient *ane, const char *name, void *data, size_t size)
{
	struct debugfs_blob_wrapper *w;

	if (IS_ERR_OR_NULL(ane_seq_dbg))
		ane_seq_dbg = debugfs_create_dir("ane_t6021_seq", NULL);
	w = devm_kzalloc(ane->dev, sizeof(*w), GFP_KERNEL);
	if (IS_ERR_OR_NULL(ane_seq_dbg) || !w || !data || !size)
		return;
	w->data = data;
	w->size = size;
	debugfs_create_blob(name, 0400, ane_seq_dbg, w);
}

static void ane_seq_publish(struct ane_rtclient *ane, unsigned int cur, unsigned int i,
			    struct ane_legacy_buffer *b)
{
	char name[16];

	snprintf(name, sizeof(name), "s%02ub%02u", cur, i);
	ane_seq_blob(ane, name, b->cpu, b->size);
}

/* Print, then (legacy_t2h_ack) hand back, every firmware-owned slot on a
 * target-to-host ring. The firmware publishes a message by writing its
 * DMA address with bit 0 clear; the host returns the slot by setting bit 0
 * and ringing the channel's doorbell bit, as the allocation ring does. */
static unsigned int ane_seq_drain_t2h(struct ane_rtclient *ane, unsigned int cur,
				      unsigned int channel)
{
	const struct ane_t6021_chman_static *c = &ane_t6021_chman_layout[channel];
	unsigned int n = 0, slot_i = ane->legacy_cmd_cursor[channel];
	void __iomem *ipi = NULL;

	if (!ane->fw || !ane->fw->boot_ipc)
		return 0;
	while (n < c->size) {
		u64 *slot = ane->fw->boot_ipc + c->off + (size_t)slot_i * 64;
		u64 hdr = READ_ONCE(slot[0]), len = READ_ONCE(slot[1]);
		dma_addr_t at = hdr & ~3ULL;
		unsigned int bi;

		if (hdr & 1)
			break;
		dma_rmb();
		dev_info(ane->dev, "SEQ %u T2H ch=%s slot=%u hdr=%016llx len=%#llx w2=%#llx\n",
			 cur, c->name, slot_i, hdr, len, READ_ONCE(slot[2]));
		for (bi = 0; bi < ane->legacy_allocated; bi++) {
			struct ane_legacy_buffer *b = &ane->legacy_buffers[bi];

			if (at < b->dma || at >= b->dma + b->size)
				continue;
			print_hex_dump(KERN_INFO, "SEQ t2h: ", DUMP_PREFIX_OFFSET, 16, 4,
				       (u8 *)b->cpu + (at - b->dma),
				       min_t(size_t, min_t(u64, len, 0x440),
					     b->dma + b->size - at), false);
			break;
		}
		n++;
		if (!legacy_t2h_ack)
			break;
		WRITE_ONCE(slot[0], hdr | 1);
		dma_wmb();
		if (!ipi)
			ipi = ioremap_np(0x285844000ull, 0xc004);
		if (ipi)
			writel(BIT(c->bit), ipi);
		slot_i = (slot_i + 1) % c->size;
		ane->legacy_cmd_cursor[channel] = slot_i;
	}
	if (ipi)
		iounmap(ipi);
	return n;
}

static void ane_seq_dump_bufs(struct ane_rtclient *ane, struct ane_seq_step *s,
			      const struct ane_seq_buf *bd, unsigned int cur, const char *tag)
{
	unsigned int i;

	for (i = 0; i < s->nbufs; i++) {
		u32 dump_len = min_t(u32, le32_to_cpu(bd[i].dump_len), ANE_SEQ_DUMP_MAX);

		if (!dump_len)
			continue;
		dma_rmb();
		dev_info(ane->dev, "SEQ %u buf %u %s dump %u bytes crc32=%08x\n", cur, i, tag,
			 dump_len, crc32_le(~0, s->buf[i]->cpu, dump_len) ^ ~0);
		print_hex_dump(KERN_INFO, "SEQ buf: ", DUMP_PREFIX_OFFSET, 16, 4,
			       s->buf[i]->cpu, dump_len, false);
	}
}

static int ane_seq_run_step(struct ane_rtclient *ane, struct ane_seq_step *steps,
			    unsigned int cur, const struct firmware *fw)
{
	const struct ane_seq_hdr *h = (const void *)fw->data;
	const struct ane_seq_buf *bd;
	const struct ane_seq_patch *pd;
	const u8 *cmd, *fill;
	struct ane_seq_step *s = &steps[cur];
	struct ane_legacy_buffer *command;
	u32 nbufs, npatch, cmd_len, timeout_ms, dump_reply, i;
	u16 opcode, channel;
	size_t need, fill_total = 0;
	int result;

	if (fw->size < sizeof(*h) || le32_to_cpu(h->magic) != ANE_SEQ_MAGIC)
		return -EINVAL;
	nbufs = le32_to_cpu(h->nbufs);
	npatch = le32_to_cpu(h->npatch);
	cmd_len = le32_to_cpu(h->cmd_len);
	opcode = le16_to_cpu(h->opcode);
	channel = le16_to_cpu(h->channel);
	timeout_ms = clamp_t(u32, le32_to_cpu(h->timeout_ms), 100, 20000);
	dump_reply = min_t(u32, le32_to_cpu(h->dump_reply), cmd_len);
	if (nbufs > ANE_SEQ_BUFS || npatch > 256 || cmd_len < 8 || cmd_len > SZ_16K ||
	    channel >= ANE_T6021_CHMAN_COUNT)
		return -EINVAL;
	need = sizeof(*h) + nbufs * sizeof(*bd) + npatch * sizeof(*pd) + cmd_len;
	if (fw->size < need)
		return -EINVAL;
	bd = (const void *)(h + 1);
	pd = (const void *)(bd + nbufs);
	cmd = (const u8 *)(pd + npatch);
	fill = cmd + cmd_len;
	for (i = 0; i < nbufs; i++)
		fill_total += le32_to_cpu(bd[i].fill_len);
	if (fw->size != need + fill_total)
		return -EINVAL;

	for (i = 0; i < nbufs; i++) {
		u32 size = round_up(max_t(u32, le32_to_cpu(bd[i].size), 1), SZ_16K);
		u32 fill_len = le32_to_cpu(bd[i].fill_len);

		if (fill_len > size)
			return -EINVAL;
		s->buf[i] = ane_rtclient_legacy_alloc(ane, size);
		if (IS_ERR(s->buf[i]))
			return PTR_ERR(s->buf[i]);
		memset(s->buf[i]->cpu, 0, size);
		memcpy(s->buf[i]->cpu, fill, fill_len);
		fill += fill_len;
		s->nbufs = i + 1;
		dev_info(ane->dev, "SEQ %u buf %u dma=%pad size=%u fill=%u\n", cur, i,
			 &s->buf[i]->dma, size, fill_len);
	}
	command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(command))
		return PTR_ERR(command);
	memset(command->cpu, 0, SZ_16K);
	memcpy(command->cpu, cmd, cmd_len);
	for (i = 0; i < npatch; i++) {
		result = ane_seq_patch_one(ane, steps, cur, command, &pd[i]);
		if (result)
			return result;
	}
	dma_wmb();
	dev_info(ane->dev, "SEQ %u send opcode=%#x len=%u channel=%u\n", cur, opcode,
		 cmd_len, channel);
	result = ane_rtclient_legacy_exchange(ane, command, cmd_len, opcode, channel,
					      timeout_ms);
	dma_rmb();
	s->reply_len = min_t(u32, cmd_len, ANE_SEQ_REPLY);
	memcpy(s->reply, command->cpu, s->reply_len);
	dev_info(ane->dev, "SEQ %u result=%d opcode=%#x status=%#x\n", cur, result, opcode,
		 s->reply[6]);
	if (dump_reply)
		print_hex_dump(KERN_INFO, "SEQ reply: ", DUMP_PREFIX_OFFSET, 16, 4,
			       s->reply, dump_reply, false);
	if (le32_to_cpu(h->settle_ms))
		msleep(min_t(u32, le32_to_cpu(h->settle_ms), 5000));
	ane_seq_dump_bufs(ane, s, bd, cur, "before-ack");
	for (i = 0; i < nbufs; i++)
		if (le32_to_cpu(bd[i].dump_len))
			ane_seq_publish(ane, cur, i, s->buf[i]);
	if (ane_seq_drain_t2h(ane, cur, 4) + ane_seq_drain_t2h(ane, cur, 6)) {
		msleep(clamp_t(u32, le32_to_cpu(h->settle_ms), 50, 5000));
		ane_seq_drain_t2h(ane, cur, 4);
		ane_seq_drain_t2h(ane, cur, 6);
		ane_seq_dump_bufs(ane, s, bd, cur, "after-ack");
	}
	return result;
}

/* One device per boot: the step table and cursor live until reboot. */
static struct ane_seq_step *ane_seq_steps;
static unsigned int ane_seq_next;
static DEFINE_MUTEX(ane_seq_lock);

static int ane_seq_continue(struct ane_rtclient *ane)
{
	int result = 0;

	mutex_lock(&ane_seq_lock);
	for (; ane_seq_next < ANE_SEQ_STEPS; ane_seq_next++) {
		const struct firmware *fw;
		char path[40];

		snprintf(path, sizeof(path), "apple/ane/seq/%02u.bin", ane_seq_next);
		if (request_firmware_direct(&fw, path, ane->dev))
			break;
		result = ane_seq_run_step(ane, ane_seq_steps, ane_seq_next, fw);
		release_firmware(fw);
		if (result) {
			dev_warn(ane->dev, "SEQ stopped at step %u: %d\n", ane_seq_next, result);
			ane_seq_next++;
			break;
		}
	}
	dev_info(ane->dev, "SEQ done next=%u result=%d\n", ane_seq_next, result);
	mutex_unlock(&ane_seq_lock);
	return result;
}

static ssize_t ane_seq_run_write(struct file *file, const char __user *buf, size_t len,
				 loff_t *ppos)
{
	int result = ane_seq_continue(file->private_data);

	return result ? result : len;
}

static const struct file_operations ane_seq_run_fops = {
	.owner = THIS_MODULE,
	.open = simple_open,
	.write = ane_seq_run_write,
};

static const struct file_operations ane_seq_pmu_fops;
static const struct file_operations ane_seq_power_fops;

static int ane_rtclient_legacy_sequence(struct ane_rtclient *ane)
{
	struct ane_t6021 *a = ane->fw;

	/* ~270 KiB and never freed: the driver is reboot-only. */
	ane_seq_steps = kvcalloc(ANE_SEQ_STEPS, sizeof(*ane_seq_steps), GFP_KERNEL);
	if (!ane_seq_steps)
		return -ENOMEM;
	/* Read-only views of firmware-visible host memory: the boot heap
	 * holds the firmware's extra-heap objects (ExeLoop engine, FSMs). */
	if (a) {
		ane_seq_blob(ane, "heap", a->boot_heap, a->boot_heap_size);
		ane_seq_blob(ane, "pool", a->boot_pool, 0x40000);
		ane_seq_blob(ane, "fwbuf", a->fw_buf, a->fw_size);
	}
	if (!IS_ERR_OR_NULL(ane_seq_dbg))
		debugfs_create_file("run", 0200, ane_seq_dbg, ane, &ane_seq_run_fops);
	debugfs_create_file("pmu", 0400, ane_seq_dbg, ane, &ane_seq_pmu_fops);
	debugfs_create_file("power_release", 0200, ane_seq_dbg, ane, &ane_seq_power_fops);
	return ane_seq_continue(ane);
}

static ssize_t ane_seq_pmu_read(struct file *file, char __user *buf, size_t len, loff_t *ppos)
{
	struct ane_rtclient *ane = file->private_data;
	struct iommu_domain *dom = iommu_get_domain_for_dev(ane->dev);
	char out[64];
	int n;

	n = scnprintf(out, sizeof(out), "pmu_iova_to_phys=%#llx\n",
		      dom ? iommu_iova_to_phys(dom, 0x28e084000ull) : 0);
	return simple_read_from_buffer(buf, len, ppos, out, n);
}

static const struct file_operations ane_seq_pmu_fops = {
	.owner = THIS_MODULE,
	.open = simple_open,
	.read = ane_seq_pmu_read,
};

/* Drop the driver's runtime PM hold so genpd can power down the compute
 * domains. The firmware's power-down poll (0x29) spins forever while genpd
 * holds them on. ane_cpu stays up: the iommu holds it separately. */
static ssize_t ane_seq_power_write(struct file *file, const char __user *buf, size_t len,
				   loff_t *ppos)
{
	struct ane_rtclient *ane = file->private_data;

	pm_runtime_put_sync(ane->dev);
	return len;
}

static const struct file_operations ane_seq_power_fops = {
	.owner = THIS_MODULE,
	.open = simple_open,
	.write = ane_seq_power_write,
};
