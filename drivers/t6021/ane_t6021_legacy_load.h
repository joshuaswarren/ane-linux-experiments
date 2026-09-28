struct ane_legacy_descriptor {
	__le32 flags;
	__le32 identity[4];
	__le32 reserved;
	__le64 address;
	__le64 size;
	__le64 tail;
};

struct ane_legacy_load_message {
	__le16 header[4];
	struct ane_legacy_descriptor sections[9];
	__le32 program_id;
	__le32 reserved;
};

static_assert(sizeof(struct ane_legacy_descriptor) == 0x30);
static_assert(sizeof(struct ane_legacy_load_message) == 0x1c0);

static int ane_rtclient_legacy_probe_opcode(struct ane_rtclient *ane, u16 opcode,
					    size_t length)
{
	struct ane_legacy_buffer *command;
	u32 *words;
	int result;

	command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(command))
		return PTR_ERR(command);
	words = command->cpu;
	dev_info(ane->dev, "LEGACY CSNE probe opcode=%#x bytes=%zu channel=IO\n",
		 opcode, length);
	result = ane_rtclient_legacy_exchange(ane, command, length, opcode, 1, 3000);
	dev_info(ane->dev,
		 "LEGACY CSNE probe opcode=%#x result=%d words=%08x %08x %08x %08x\n",
		 opcode, result, READ_ONCE(words[0]), READ_ONCE(words[1]),
		 READ_ONCE(words[2]), READ_ONCE(words[3]));
	return result;
}

struct ane_legacy_section_spec {
	const char *name;
	u32 identity;
	size_t size;
};

static int ane_rtclient_legacy_stage_section(struct ane_rtclient *ane,
					     const struct ane_legacy_section_spec *spec,
					     struct ane_legacy_descriptor *desc)
{
	struct ane_legacy_buffer *section;
	const struct firmware *fw;
	char path[96];
	int result;

	section = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(section))
		return PTR_ERR(section);
	snprintf(path, sizeof(path), "apple/ane/h14conv/%s", spec->name);
	result = request_firmware_direct(&fw, path, ane->dev);
	if (result)
		return result;
	memcpy(section->cpu, fw->data, min_t(size_t, fw->size, section->size));
	release_firmware(fw);
	desc->flags = cpu_to_le32(1);
	desc->identity[0] = cpu_to_le32(spec->identity);
	desc->reserved = cpu_to_le32(0);
	desc->address = cpu_to_le64(section->dma);
	desc->size = cpu_to_le64(spec->size);
	desc->tail = cpu_to_le64(0);
	dev_info(ane->dev, "LEGACY load section %s identity=%u dma=%pad size=%zu\n",
		 spec->name, spec->identity, &section->dma, spec->size);
	return 0;
}

static int ane_rtclient_legacy_load_program_outer_on(struct ane_rtclient *ane,
						     unsigned int channel);

static int ane_rtclient_legacy_load_program(struct ane_rtclient *ane)
{
	/* Exact-size hypothesis: the 0x200 CmdProcessor likely requires
	 * the full 0x1c0 driver message (9 slots), like CONFIG_GET
	 * requires exact 16. Six payloads staged, three unknown slots
	 * present-but-absent (flags=0, skipped by the walker). */
	static const struct ane_legacy_section_spec specs[9] = {
		{ "generic.bin", 1, 616 },
		{ "kernel.bin", 2, 8192 },
		{ "text.bin", 3, 408 },
		{ "operation.bin", 4, 1040 },
		{ "procedure.bin", 5, 56 },
		{ NULL, 0, 0 },
		{ "text-property.bin", 7, 40 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
	};
	struct ane_legacy_buffer *command;
	struct ane_legacy_load_message *message;
	unsigned int i;
	int result;

	command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(command))
		return PTR_ERR(command);
	message = command->cpu;
	memset(message, 0, sizeof(*message));
	message->program_id = cpu_to_le32(U32_MAX);
	for (i = 0; i < ARRAY_SIZE(specs); i++) {
		if (!specs[i].name)
			continue;
		result = ane_rtclient_legacy_stage_section(ane, &specs[i],
							   &message->sections[i]);
		if (result)
			return result;
	}
	dev_info(ane->dev, "LEGACY load 0x200 exact bytes=%zu sections=6+3absent\n",
		 sizeof(*message));
	result = ane_rtclient_legacy_exchange(ane, command, sizeof(*message),
					      0x200, 1, 5000);
	dev_info(ane->dev, "LEGACY LOAD_PROGRAM result=%d program_id=%#x status=%u\n",
		 result, le32_to_cpu(message->program_id),
		 le16_to_cpu(message->header[3]));
	print_hex_dump(KERN_INFO, "LEGACY load reply: ", DUMP_PREFIX_OFFSET,
		       16, 1, message, 64, false);
	if (!result && le32_to_cpu(message->program_id) == U32_MAX)
		return -EPROTO;
	return result;
}
static int ane_rtclient_legacy_load_program_id0(struct ane_rtclient *ane)
{
	static const struct ane_legacy_section_spec specs[9] = {
		{ "generic.bin", 0, 616 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
		{ NULL, 0, 0 },
	};
	struct ane_legacy_buffer *command;
	struct ane_legacy_load_message *message;
	unsigned int i;
	int result;

	command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(command))
		return PTR_ERR(command);
	message = command->cpu;
	memset(message, 0, sizeof(*message));
	message->program_id = cpu_to_le32(U32_MAX);
	for (i = 0; i < ARRAY_SIZE(specs); i++) {
		if (!specs[i].name)
			continue;
		result = ane_rtclient_legacy_stage_section(ane, &specs[i],
							   &message->sections[i]);
		if (result)
			return result;
	}
	dev_info(ane->dev, "LEGACY load 0x200 id0 bytes=%zu\n", sizeof(*message));
	result = ane_rtclient_legacy_exchange(ane, command, sizeof(*message),
					      0x200, 1, 15000);
	dev_info(ane->dev, "LEGACY LOAD_PROGRAM id0 result=%d program_id=%#x status=%u\n",
		 result, le32_to_cpu(message->program_id),
		 le16_to_cpu(message->header[3]));
	print_hex_dump(KERN_INFO, "LEGACY load id0 reply: ", DUMP_PREFIX_OFFSET,
		       16, 1, message, 64, false);
	if (!result && le32_to_cpu(message->program_id) == U32_MAX)
		return -EPROTO;
	return result;
}
static void ane_rtclient_legacy_reclaim(struct ane_rtclient *ane,
					 unsigned int channel)
{
	u64 *io;
	u64 header;

	if (!ane->fw || !ane->fw->boot_ipc || channel >= ANE_T6021_CHMAN_COUNT)
		return;
	io = ane->fw->boot_ipc + ane_t6021_chman_layout[channel].off;
	header = READ_ONCE(io[0]);
	dev_info(ane->dev, "LEGACY reclaim ch=%u io0=%016llx\n", channel, header);
	if (header & 1)
		return;
	WRITE_ONCE(io[0], header | 1);
	dma_wmb();
	dev_info(ane->dev, "LEGACY reclaim forced bit0 now=%016llx\n",
		 READ_ONCE(io[0]));
}
static int ane_rtclient_legacy_arm_and_load(struct ane_rtclient *ane)
{
	dev_info(ane->dev, "LEGACY PING bypass: sending LOAD_PROGRAM 0x200\n");
	return ane_rtclient_legacy_load_program(ane);
}
static int ane_rtclient_legacy_load_program_outer_on(struct ane_rtclient *ane,
						     unsigned int channel)
{
	/* Outer command shape per firmware 0x3ebd4: section count at
	 * +0x28, flag byte at +0x30, nonzero words at +0x48/+0x50,
	 * descriptors (0x30 stride) at +0x60. Packing sections at +0x08
	 * puts size-lo (616) in the count field, so the walker scans
	 * garbage. The exchange stamps the opcode halfword at +0x04. */
	static const struct ane_legacy_section_spec specs[] = {
		{ "generic.bin", 1, 616 },
		{ "kernel.bin", 2, 8192 },
		{ "text.bin", 3, 408 },
		{ "operation.bin", 4, 1040 },
		{ "procedure.bin", 5, 56 },
		{ "text-property.bin", 7, 40 },
	};
	struct ane_legacy_buffer *command;
	u8 *cmd;
	size_t length;
	unsigned int i;
	int result;

	command = ane_rtclient_legacy_alloc(ane, SZ_16K);
	if (IS_ERR(command))
		return PTR_ERR(command);
	cmd = command->cpu;
	length = 0x60 + ARRAY_SIZE(specs) * sizeof(struct ane_legacy_descriptor);
	memset(cmd, 0, length);
	*(__le32 *)(cmd + 0x28) = cpu_to_le32(ARRAY_SIZE(specs));
	cmd[0x30] = 1;
	*(__le64 *)(cmd + 0x48) = cpu_to_le64(command->dma);
	*(__le64 *)(cmd + 0x50) = cpu_to_le64(command->dma + 0x60);
	for (i = 0; i < ARRAY_SIZE(specs); i++) {
		result = ane_rtclient_legacy_stage_section(ane, &specs[i],
			(struct ane_legacy_descriptor *)(cmd + 0x60 + i * 0x30));
		if (result)
			return result;
	}
	dev_info(ane->dev, "LEGACY load 0x200 outer bytes=%zu sections=%zu channel=%u\n",
		 length, ARRAY_SIZE(specs), channel);
	result = ane_rtclient_legacy_exchange(ane, command, length,
					      0x200, channel, 5000);
	dev_info(ane->dev, "LEGACY LOAD_PROGRAM result=%d status=%u\n",
		 result, le16_to_cpu(((__le16 *)cmd)[3]));
	print_hex_dump(KERN_INFO, "LEGACY load reply: ", DUMP_PREFIX_OFFSET,
		       16, 1, cmd, 64, false);
	return result;
}
