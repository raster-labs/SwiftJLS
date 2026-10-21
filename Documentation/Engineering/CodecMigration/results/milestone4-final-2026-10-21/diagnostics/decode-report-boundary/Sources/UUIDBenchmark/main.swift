import Foundation
import Dispatch
import UUIDMicroCore

struct Failure: Error {}
guard CommandLine.arguments.count == 4,
      let warmups = Int(CommandLine.arguments[2]), let iterations = Int(CommandLine.arguments[3]),
      warmups >= 0, iterations > 0 else { throw Failure() }
let mode = CommandLine.arguments[1]
@inline(never) func operation() throws -> UInt {
    switch mode {
    case "uuid": return consumeUUID(makeFoundationUUID())
    case "reference": return consumeReferenceIdentity(makeReferenceIdentity())
    case "random":
        if #available(macOS 26.4, *) { return consumeUUID(makeRandomUUID()) }
        throw Failure()
    default: throw Failure()
    }
}
var checksum: UInt = 0
for _ in 0..<warmups { checksum &+= try operation() }
var elapsed: [Double] = []
for _ in 0..<iterations {
    let start = DispatchTime.now().uptimeNanoseconds
    checksum &+= try operation()
    elapsed.append(Double(DispatchTime.now().uptimeNanoseconds - start) / 1_000_000_000)
}
let result: [String: Any] = ["mode":mode,"warmups":warmups,"iterations":iterations,"seconds":elapsed,"checksum":String(checksum),"scope":"Construction plus consumption/destruction and timer overhead. Reference identity is a diagnostic only, forbidden by current UUID lease contract. random requires macOS26.4 and is not an OS26.0 production alternative."]
print(String(decoding: try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys]), as: UTF8.self))
