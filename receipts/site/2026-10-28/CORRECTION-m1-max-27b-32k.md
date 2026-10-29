# Correction: the 32k runs in the M1 Max 27B receipt were run on the Intel Arc Pro B60

The file `macbook-pro-m1-max-16-qwen3.8-27b-ud-q4km-llamacpp-vulkan.json`, in the version committed as 22a1d29, carries two sizes: 8192 and 32768.

- The 8192 runs were measured on the 16-inch MacBook Pro's Apple GPU (M1 Max). Their receipt is the earlier version of this file, commit e5187a9, which the site row for that cell links to.
- The 32768 runs (prefill about 141 to 144 tokens/s, decode about 8.4 tokens/s) were measured on the Intel Arc Pro B60 eGPU attached to the same laptop. They were filed under the M1 Max by a mistake in the ingest job, which keyed receipts by host only, and listed on the site for a few minutes before being removed.
- The B60 runs have their own receipt, `arc-pro-b60-24-qwen3.8-27b-ud-q4km-llamacpp-vulkan.json`, and their own rows on the site. Use that one.

The file is left as committed (receipts are not rewritten). The ingest job now files a receipt under the device named in the receipt and refuses one whose device is not exactly one known kind.
