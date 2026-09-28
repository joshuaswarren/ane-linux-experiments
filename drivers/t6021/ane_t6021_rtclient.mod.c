#include <linux/module.h>
#include <linux/export-internal.h>
#include <linux/compiler.h>

MODULE_INFO(name, KBUILD_MODNAME);

__visible struct module __this_module
__section(".gnu.linkonce.this_module") = {
	.name = KBUILD_MODNAME,
	.init = init_module,
#ifdef CONFIG_MODULE_UNLOAD
	.exit = cleanup_module,
#endif
	.arch = MODULE_ARCH_INIT,
};

KSYMTAB_DATA(ane_t6021_rtb_mode, "");
SYMBOL_FLAGS(ane_t6021_rtb_mode, 0x01);

MODULE_INFO(depends, "");

MODULE_ALIAS("of:N*T*Capple,t6021-ane");
MODULE_ALIAS("of:N*T*Capple,t6021-aneC*");
