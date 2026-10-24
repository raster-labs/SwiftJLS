import Foundation

public final class ReferenceIdentity: Sendable {
    fileprivate init() {}
}
@inline(never) public func makeReferenceIdentity() -> ReferenceIdentity { ReferenceIdentity() }
@inline(never) public func consumeReferenceIdentity(_ value: consuming ReferenceIdentity) -> UInt {
    UInt(bitPattern: ObjectIdentifier(value))
}
@inline(never) public func makeFoundationUUID() -> UUID { UUID() }
@inline(never) public func consumeUUID(_ value: consuming UUID) -> UInt {
    let bytes = value.uuid
    return UInt(bytes.0) ^ (UInt(bytes.15) << 8)
}
@available(macOS 26.4, *)
@inline(never) public func makeRandomUUID() -> UUID {
    var generator = SystemRandomNumberGenerator()
    return UUID.random(using: &generator)
}
