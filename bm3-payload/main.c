/* BM3 milestone-0 payload (your 6828): a bare-metal hello on T8103-class
 * Apple Silicon, chainloaded by aura proxyclient `chainload.py -r` into the
 * loader's inherited RAM. Standalone code on the unmodified loader ABI - no
 * m1n1 sources, nothing runs on the host OS.
 *
 * Observable output, two channels:
 *  - framebuffer: 8 colour bars, white border, "BM3" glyphs (KVM/screen).
 *  - BootArgs.cmdline: "bm3-payload-alive" signature readable over the proxy
 *    (iface readmem) when no display is wired.
 */
typedef unsigned long u64;
typedef unsigned int u32;
typedef unsigned char u8;

register u64 ba asm("x19");

#define BA_VIDEO_BASE   0x28
#define BA_VIDEO_STRIDE 0x38
#define BA_VIDEO_WIDTH  0x40
#define BA_VIDEO_HEIGHT 0x48
#define BA_CMDLINE      0x70

static const u8 glyph_B[8] = {0xfc,0x66,0x66,0x7c,0x66,0x66,0x66,0xfc};
static const u8 glyph_M[8] = {0xc3,0xe7,0xff,0xdb,0xc3,0xc3,0xc3,0xc3};
static const u8 glyph_3[8] = {0x7c,0xc6,0x06,0x0e,0x1c,0x06,0xc6,0x7c};

static void draw_glyph(volatile u32 *fb, u64 row_words, const u8 *g,
                       u64 x0, u64 y0, u32 color, u64 scale)
{
    for (u64 r = 0; r < 8; r++)
        for (u64 c = 0; c < 8; c++)
            if (g[r] & (0x80 >> c))
                for (u64 dy = 0; dy < scale; dy++)
                    for (u64 dx = 0; dx < scale; dx++)
                        fb[(y0 + r * scale + dy) * row_words + x0 + c * scale + dx] = color;
}

void bm3_main(void)
{
    volatile u64 *args = (volatile u64 *)ba;
    u64 fb     = args[BA_VIDEO_BASE / 8];
    u64 stride = args[BA_VIDEO_STRIDE / 8];
    u64 width  = args[BA_VIDEO_WIDTH / 8];
    u64 height = args[BA_VIDEO_HEIGHT / 8];
    if (fb && width && height) {
        if (stride < width * 4)
            stride = width * 4;
        u64 rows = stride / 4;
        volatile u32 *pix = (volatile u32 *)fb;
        static const u32 bars[8] = {
            0xffff0000, 0xffff8000, 0xffffe000, 0xff00ff00,
            0xff00ffff, 0xff0000ff, 0xffff00ff, 0xffffffff,
        };
        for (u64 y = 0; y < height; y++) {
            u32 c = bars[(y * 8 / height) & 7];
            for (u64 x = 0; x < width; x++)
                pix[y * rows + x] = c;
        }
        for (u64 x = 0; x < width; x++)
            for (u64 y = 0; y < 16; y++) {
                pix[y * rows + x] = 0xffffffff;
                pix[(height - 1 - y) * rows + x] = 0xffffffff;
            }
        for (u64 y = 0; y < height; y++)
            for (u64 x = 0; x < 16; x++) {
                pix[y * rows + x] = 0xffffffff;
                pix[y * rows + width - 1 - x] = 0xffffffff;
            }
        draw_glyph(pix, rows, glyph_B, 64,      64, 0xffffffff, 12);
        draw_glyph(pix, rows, glyph_M, 64 + 96,  64, 0xffffffff, 12);
        draw_glyph(pix, rows, glyph_3, 64 + 192, 64, 0xffffffff, 12);
    }
    static const char sig[] = "bm3-payload-alive";
    volatile char *cmd = (volatile char *)ba + BA_CMDLINE;
    for (u64 i = 0; i < sizeof(sig); i++)
        cmd[i] = sig[i];
    __asm__ volatile("dsb sy\n\tisb");
}
