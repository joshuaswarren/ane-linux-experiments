#import <Foundation/Foundation.h>

#include <cstdio>
#include <unistd.h>

typedef unsigned int ANECStatus;
extern "C" int ANECCompile(NSDictionary *options, NSDictionary *flags,
                           void (^callback)(ANECStatus, NSDictionary *));

int main(int argc, char **argv) {
  @autoreleasepool {
    if (argc < 3 || argc > 4) {
      std::fprintf(stderr, "usage: %s CAPTURE_DIR OUTPUT_DIR [TARGET_ARCH]\n",
                   argv[0]);
      return 2;
    }

    NSFileManager *files = NSFileManager.defaultManager;
    NSString *capture = [[NSString stringWithUTF8String:argv[1]]
        stringByStandardizingPath];
    NSString *output = [[NSString stringWithUTF8String:argv[2]]
        stringByStandardizingPath];
    NSString *architecture = argc == 4
        ? [NSString stringWithUTF8String:argv[3]]
        : @"h13";
    NSString *mil = [capture stringByAppendingPathComponent:@"model.mil"];
    NSString *weights = [capture stringByAppendingPathComponent:@"weights.bin"];
    if (![files isReadableFileAtPath:mil] || ![files isReadableFileAtPath:weights]) {
      std::fprintf(stderr, "capture must contain readable model.mil and weights.bin\n");
      return 2;
    }
    NSError *directoryError = nil;
    if (![files createDirectoryAtPath:output
          withIntermediateDirectories:YES
                           attributes:nil
                                error:&directoryError]) {
      std::fprintf(stderr, "cannot create output directory: %s\n",
                   directoryError.localizedDescription.UTF8String);
      return 2;
    }
    if (![capture hasSuffix:@"/"]) capture = [capture stringByAppendingString:@"/"];
    if (![output hasSuffix:@"/"]) output = [output stringByAppendingString:@"/"];

    NSDictionary *network = @{
      @"NetworkSourceFileName": @"model.mil",
      @"NetworkSourcePath": capture,
    };
    NSDictionary *options = @{
      @"InputNetworks": @[network],
      @"OutputFilePath": output,
      @"OutputFileName": @"model.hwx",
    };
    NSDictionary *flags = @{
      @"TargetArchitecture": architecture,
    };

    __block ANECStatus callbackStatus = 0;
    __block bool callbackCalled = false;
    int result = ANECCompile(options, flags,
        ^(ANECStatus status, NSDictionary *) {
          callbackCalled = true;
          callbackStatus = status;
          std::fprintf(stderr, "callback_status=%u\n", status);
          std::fflush(stderr);
        });
    std::printf("ANECCompile=%d callback_status=%u\n", result, callbackStatus);
    std::fflush(stdout);
    if (result != 0 || (callbackCalled && callbackStatus != 0)) return 1;

    NSString *artifact = [output stringByAppendingPathComponent:@"model.hwx"];
    for (int attempt = 0; attempt < 600; ++attempt) {
      NSDictionary *attributes = [files attributesOfItemAtPath:artifact error:nil];
      if ([attributes fileSize] > 0) return 0;
      usleep(100000);
    }
    std::fprintf(stderr, "compiler did not create model.hwx within 60 seconds\n");
    return 1;
  }
}
