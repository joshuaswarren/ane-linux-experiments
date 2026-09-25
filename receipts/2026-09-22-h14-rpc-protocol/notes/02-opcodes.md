# Full CSNE_CMD opcode table (H14 selene fw; ids from w2/fw_cmd_table.json)

id    name                                                   fw-cstr    corroboration
0x0000CSNE_CMD_START                                         0xa000d    json MEDIUM
0x0001CSNE_CMD_STOP                                          0xa1588    json MEDIUM
0x0002CSNE_CMD_RESET                                         0xa1596    json MEDIUM
0x0003CSNE_CMD_CONFIG_GET                                    0xa15a5    json MEDIUM
0x0004CSNE_CMD_PRINT_ENABLE                                  0xa15b9    json MEDIUM
0x0005CSNE_CMD_REG_FILE_LOAD                                 0xa15cf    json MEDIUM
0x0006CSNE_CMD_BUILDINFO                                     0xa15e6    json MEDIUM
0x0007CSNE_CMD_TIMEPROFILE_START                             0xa15f9    json MEDIUM
0x0008CSNE_CMD_TIMEPROFILE_STOP                              0xa1614    json MEDIUM
0x0009CSNE_CMD_TIMEPROFILE_SHOW                              0xa162e    json MEDIUM
0x000aCSNE_CMD_FW_RUN_MODE                                   0xa1648    json MEDIUM
0x000bCSNE_CMD_POWER_DOWN                                    0xa165d    json MEDIUM
0x000cCSNE_CMD_SET_SNE_PMU_BASE                              0xa1671    json MEDIUM
0x000dCSNE_CMD_SET_SNE_RPC_CHECK_CMD                         0xa168b    json MEDIUM
0x000eCSNE_CMD_RPC_ENABLE                                    0xa16aa    json MEDIUM
0x000fCSNE_CMD_PLATFORM_INFO                                 0xa16be    json MEDIUM
0x0010CSNE_CMD_BOOT                                          0xa16d5    json MEDIUM
0x0011CSNE_CMD_PING                                          0xa16e3    json MEDIUM
0x0012CSNE_CMD_CONFIG_GET_EXT                                0xa16f1    json MEDIUM
0x0013CSNE_CMD_POWER_DEVICE_ON                               0xa1709    json MEDIUM
0x0014CSNE_CMD_POWER_DEVICE_OFF                              0xa1722    json MEDIUM
0x0015CSNE_CMD_IPC_ENDPOINT_SET                              0xa173c    json MEDIUM
0x0016CSNE_CMD_IPC_ENDPOINT_UNSET                            0xa1756    json MEDIUM
0x0017CSNE_CMD_CH_INFO_GET                                   0xa1772    json MEDIUM
0x0018CSNE_CMD_CH_BUFFER_RECYCLE_MODE_SET                    0xa1787    json MEDIUM
0x0019CSNE_CMD_CH_BUFFER_RECYCLE_START                       0xa17ab    json MEDIUM
0x001aCSNE_CMD_CH_BUFFER_RECYCLE_STOP                        0xa17cc    json MEDIUM
0x001bCSNE_CMD_CH_BUFFER_RETURN                              0xa17ec    json MEDIUM
0x001cCSNE_CMD_CH_BUFFER_POOL_CONFIG_GET                     0xa1806    json MEDIUM
0x001dCSNE_CMD_CH_BUFFER_POOL_CONFIG_SET                     0xa1829    json MEDIUM
0x001eCSNE_CMD_CH_DATA_FILE_LOAD                             0xa184c    json MEDIUM
0x001fCSNE_CMD_CH_PROPERTY_WRITE                             0xa1867    json MEDIUM
0x0020CSNE_CMD_CH_PROPERTY_READ                              0xa1882    json MEDIUM
0x0021CSNE_CMD_TRACE_ENABLE                                  0xa189c    json MEDIUM
0x0022CSNE_CMD_RESOURCE_INFO_GET                             0xa18b2    json MEDIUM
0x0023CSNE_CMD_STATS_BUFFER_SIZE_GET                         0xa18cd    json MEDIUM
0x0024CSNE_CMD_SUSPEND                                       0xa18ec    json MEDIUM
0x0025CSNE_CMD_DSID_SET                                      0xa18fd    json MEDIUM
0x0026CSNE_CMD_MCACHE_SIZE_GET                               0xa190f    json MEDIUM
0x0027CSNE_CMD_SECURE_MODE_START                             0xa1928    json MEDIUM
0x0028CSNE_CMD_SECURE_MODE_STOP                              0xa1943    json MEDIUM
0x0029CSNE_CMD_SET_SNE_PMU_BASE2                             0xa195d    json MEDIUM
0x002aCSNE_CMD_IPC_ENDPOINT_SET2                             0xa1978    json MEDIUM
0x002bCSNE_CMD_IPC_ENDPOINT_UNSET2                           0xa1993    json MEDIUM
0x002cCSNE_CMD_CH_DATA_FILE_LOAD2                            0xa19b0    json MEDIUM
0x002dCSNE_CMD_SET_DYNAMIC_POWERGATE                         0xa19cc    json MEDIUM
0x002eCSNE_CMD_ANE_DEFAULT_SETTING_SET                       0xa19eb    json MEDIUM
0x002fCSNE_CMD_INIT_SHARED_EVENT_INFO                        0xa1a0c    json MEDIUM
0x0030CSNE_CMD_EXCLAVE_MODE_START                            0xa1a2c    json MEDIUM
0x0031CSNE_CMD_EXCLAVE_MODE_STOP                             0xa1a48    json MEDIUM
0x0032CSNE_CMD_QUIESCE_STATE                                 0xa1a63    json MEDIUM
0x0033CSNE_CMD_CPU_LOAD_GET                                  0xa1a7a    json MEDIUM
0x0034CSNE_CMD_SECURE_MODE_RESUME_TRANSITION                 0xa1a90    json MEDIUM
0x0035CSNE_CMD_RESUME                                        0xa1ab7    json MEDIUM
0x0100CSNE_CMD_CH_ERROR_NOTIFICATION                         0xa1ac7    json MEDIUM
0x0101CSNE_CMD_CH_POWER_CONTROL                              0xa1ae6    json MEDIUM
0x0102CSNE_CMD_CH_SIGNPOST_NOTIFICATION                      0xa1b00    json MEDIUM
0x0103CSNE_CMD_CH_SIGNPOST_NOTIFICATION_GROUP                0xa1b22    json MEDIUM
0x0104CSNE_CMD_CH_RESET_NOTIFICATION                         0xa1b4a    json MEDIUM
0x0105CSNE_CMD_CH_SIGNPOST64_NOTIFICATION                    0xa1b69    json MEDIUM
0x0106CSNE_CMD_CH_SIGNPOST64_NOTIFICATION_GROUP              0xa1b8d    json MEDIUM
0x0107CSNE_CMD_CPU_LOAD_NOTIFICATION                         0xa1bb7    json MEDIUM
0x0108CSNE_CMD_TM_SYNC_ERR_NOTIFICATION                      0xa1bd6    json MEDIUM
0x0200CSNE_CMD_LOAD_PROGRAM                                  0xa1bf8    json MEDIUM
0x0201CSNE_CMD_UNLOAD_PROGRAM                                0xa1c0e    json MEDIUM
0x0202CSNE_CMD_CREATE_PROCESS                                0xa1c26    json MEDIUM
0x0203CSNE_CMD_TERMINATE_PROCESS                             0xa1c3e    json MEDIUM
0x0204CSNE_CMD_PROCEDURE_CALL                                0xa1c59    json MEDIUM
0x0205CSNE_CMD_LOAD_AFPP                                     0xa1c71    json MEDIUM
0x0206CSNE_CMD_UNLOAD_AFPP                                   0xa1c84    json MEDIUM
0x0207CSNE_CMD_PROGRAM_INTERFACE_VERSION_CHECK               0xa1c99    json MEDIUM
0x0208CSNE_CMD_PROCEDURE_CALL_CACHE_REQUEST                  0xa1cc2    json MEDIUM
0x0209CSNE_CMD_PROCEDURE_CALL_TRIGGER_CACHE_REQUEST          0xa1ce8    json MEDIUM
0x020aCSNE_CMD_PROCEDURE_CALL_RECYCLE_OUTPUT_BUFFER          0xa1d16    json MEDIUM
0x020bCSNE_CMD_PROCEDURE_CALL_INVALIDATE_CACHE_REQUEST       0xa1d44    json MEDIUM
0x020cCSNE_CMD_PROCEDURE_CALL_WITH_CUSTOM_BARS               0xa1d75    json MEDIUM
0x020dCSNE_CMD_PREMAP_BUFFER                                 0xa1d9e    json MEDIUM
0x020eCSNE_CMD_PROCEDURE_CALL_CACHE_REQUEST_WITH_CUSTOM_BARS 0xa1db5    json MEDIUM
0x020fCSNE_CMD_PROCEDURE_CALL_CACHE_REQUEST_WITH_SHARED_EVENTS0xa1dec    json MEDIUM
0x0210CSNE_CMD_FORCE_DISABLE_CACHE_REQUESTS                  0xa1e25    json MEDIUM
0x0211CSNE_CMD_PROCEDURE_CALL_WITH_SIGNAL_EVENTS             0xa1e4b    json MEDIUM
0x0212CSNE_CMD_SET_ACTIVE_CACHE_REQUEST_IN_GROUP             0xa1e76    json MEDIUM
0x0213CSNE_CMD_SET_SIGNAL_EVENTS                             0xa1ea1    json MEDIUM
0x0300CSNE_CMD_PROGRAM_EVENT                                 0xa1ebc    json MEDIUM
0x0301CSNE_CMD_USER_EVENT                                    0xa1ed3    json MEDIUM
0x0302CSNE_CMD_DBG_EVENT                                     0xa1ee7    json MEDIUM
0x0303CSNE_CMD_DATA_CHAINING_EVENT                           0xa1efa    json MEDIUM
0x0304CSNE_CMD_PREFETCH_DSID_EVENT                           0xa1f17    json MEDIUM
0x0305CSNE_CMD_SECURE_MODE_EVENT                             0xa1f34    json MEDIUM
0x0400CSNE_CMD_REQUEST_PROGRAM_ID                            0xa1f4f    kext imm HIGH
0x0401CSNE_CMD_RETURN_PROGRAM_ID                             0xa1f6b    kext imm HIGH
0x0402CSNE_CMD_REQUEST_PROCESS_ID                            0xa1f86    kext imm HIGH
0x0403CSNE_CMD_RETURN_PROCESS_ID                             0xa1fa2    kext imm HIGH
0x0404CSNE_CMD_INFERENCE_CALL                                0xa1fbd    kext imm HIGH
0x7000CSNE_CMD_BACK_CHANNEL_RPC                              0xa1fd5    json MEDIUM
0xff00CSNE_CMD_DEBUG_COMMAND_DATA_CHECK                      0xa1fef    kext imm HIGH
-     CSNE_CMD_IPC_ENDPOINT_TYPE_DATA_CHAINING               0xa6ab2    
-     CSNE_CMD_IPC_ENDPOINT_TYPE_DATA_CHAINING               0xa6ae9    
0x020fCSNE_CMD_PROCEDURE_CALL_CACHE_REQUEST_WITH_SHARED_EVENTS0xac37c    json MEDIUM

H13 styx fw contains the same 96 names (strict superset incl 1 const-only name) => namespace stable across generations. HIGH.

Kext sendSetupCmd (0x95e4314) semantics check: host sends 0x401 RETURN_PROGRAM_ID carrying a program id @+0x1c; sends 0x400/0x402 as requests and reads reply param @+0x1c / @+0x20. Matches table roles. HIGH for 0x400-0x404.
