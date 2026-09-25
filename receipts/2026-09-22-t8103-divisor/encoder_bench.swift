import Foundation
import CoreML

// T8103 macOS encoder divisor bench: whole Parakeet encoder via CoreML.
// usage: encoder_bench <model.mlpackage> <feat_f32.bin> <mask_i32.bin> <units: all|ane|cpu> <warmups> <reps> <dump_out.bin>

func die(_ m: String) -> Never { FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(1) }

let a = CommandLine.arguments
guard a.count == 8 else { die("args: model feat mask units warmups reps dump") }
let modelURL = URL(fileURLWithPath: a[1])
let unitsStr = a[4]
let warmups = Int(a[5])!
let reps = Int(a[6])!
let dumpPath = a[7]

let units: MLComputeUnits
switch unitsStr {
case "all": units = .all
case "ane": units = .cpuAndNeuralEngine
case "cpu": units = .cpuOnly
default: die("bad units")
}

// compile
let t0 = Date()
let compiledURL = try MLModel.compileModel(at: modelURL)
let dest = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("t8103-enc-\(unitsStr)-\(UUID().uuidString).mlmodelc")
try FileManager.default.moveItem(at: compiledURL, to: dest)
let compileMs = -t0.timeIntervalSinceNow * 1000

let cfg = MLModelConfiguration()
cfg.computeUnits = units
let tl = Date()
let model = try MLModel(contentsOf: dest, configuration: cfg)
let loadMs = -tl.timeIntervalSinceNow * 1000

// Actual per-op placement from CoreML's own plan (macOS 14.4+), not the requested label.
var placement: [String: Int] = [:]
let sem = DispatchSemaphore(value: 0)
Task.detached {
    defer { sem.signal() }
    guard let plan = try? await MLComputePlan.load(contentsOf: dest, configuration: cfg),
          case let .program(prog) = plan.modelStructure,
          let main = prog.functions["main"] else { return }
    for op in main.block.operations {
        guard let u = plan.deviceUsage(for: op)?.preferred else { continue }
        let k: String
        switch u {
        case .neuralEngine: k = "ane"
        case .gpu: k = "gpu"
        case .cpu: k = "cpu"
        @unknown default: k = "other"
        }
        placement[k, default: 0] += 1
    }
}
sem.wait()

// inputs
let featData = try Data(contentsOf: URL(fileURLWithPath: a[2]))
let maskData = try Data(contentsOf: URL(fileURLWithPath: a[3]))
let featCount = 1 * 3000 * 128
let featArr = try MLMultiArray(shape: [1, 3000, 128] as [NSNumber], dataType: .float32)
let maskArr = try MLMultiArray(shape: [1, 3000] as [NSNumber], dataType: .int32)
memcpy(featArr.dataPointer, (featData as NSData).bytes, featCount * 4)
memcpy(maskArr.dataPointer, (maskData as NSData).bytes, 3000 * 4)
let featDesc = model.modelDescription
let inpName = featDesc.inputDescriptionsByName.keys.sorted().first { $0.contains("features") }!
let maskName = featDesc.inputDescriptionsByName.keys.sorted().first { $0.contains("mask") }!
let provider = try MLDictionaryFeatureProvider(dictionary: [inpName: MLFeatureValue(multiArray: featArr), maskName: MLFeatureValue(multiArray: maskArr)])

func predict() throws -> (MLMultiArray, MLMultiArray, Double) {
    let s = Date()
    let out = try model.prediction(from: provider)
    let ms = -s.timeIntervalSinceNow * 1000
    let hidden = out.featureValue(for: "encoder_hidden")!.multiArrayValue!
    let emask = out.featureValue(for: "encoder_mask")!.multiArrayValue!
    return (hidden, emask, ms)
}

// warmups
var last = try predict()
for _ in 1..<warmups { last = try predict() }

var times: [Double] = []
for _ in 0..<reps {
    let (h, m, ms) = try predict()
    times.append(ms)
    last = (h, m, ms)
}

// dump last hidden (float32) + mask (int32)
let h = last.0
let n = h.count
let outData = Data(bytes: h.dataPointer, count: n * MemoryLayout<Float>.size)
try outData.write(to: URL(fileURLWithPath: dumpPath))
var maskOut = [Int32](repeating: 0, count: last.1.count)
for i in 0..<last.1.count { maskOut[i] = last.1[i].int32Value }
try Data(bytes: maskOut, count: maskOut.count * 4).write(to: URL(fileURLWithPath: dumpPath + ".mask"))

// mean of hidden for a cheap sanity figure
var sum = 0.0
for i in stride(from: 0, to: n, by: 97) { sum += h[i].doubleValue }

times.sort()
let median = times[times.count / 2]
let minT = times.first!, maxT = times.last!
let mean = times.reduce(0, +) / Double(times.count)
print("{\"units\":\"\(unitsStr)\",\"compile_ms\":\(String(format: "%.1f", compileMs)),\"load_ms\":\(String(format: "%.1f", loadMs)),\"placement\":{\(placement.sorted { $0.key < $1.key }.map { "\"\($0.key)\":\($0.value)" }.joined(separator: ","))},\"reps\":\(reps),\"median_ms\":\(String(format: "%.2f", median)),\"min_ms\":\(String(format: "%.2f", minT)),\"max_ms\":\(String(format: "%.2f", maxT)),\"mean_ms\":\(String(format: "%.2f", mean)),\"hidden_stride_mean\":\(String(format: "%.6f", sum / Double((n + 96) / 97))),\"hidden_count\":\(n),\"mask_sum\":\(maskOut.reduce(0, +))}")
print("times_ms [\(times.map { String(format: "%.2f", $0) }.joined(separator: ", "))]")
