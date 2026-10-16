import Foundation
import AVFoundation
import CoreGraphics

let a = CommandLine.arguments
guard a.count >= 5 else { print("usage: scan <mp4> <start> <end> <step>"); exit(1) }
let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = CMTime(seconds: 0.3, preferredTimescale: 600)
gen.requestedTimeToleranceAfter  = CMTime(seconds: 0.3, preferredTimescale: 600)
gen.maximumSize = CGSize(width: 320, height: 180)
let W = 80, H = 45
let cs = CGColorSpaceCreateDeviceGray()
var t = Double(a[2])!; let end = Double(a[3])!; let step = Double(a[4])!
print("sec,mean,whitefrac,satmean")
while t <= end {
    guard let img = try? gen.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil) else { t += step; continue }
    var buf = [UInt8](repeating: 0, count: W*H)
    buf.withUnsafeMutableBytes { p in
        let ctx = CGContext(data: p.baseAddress, width: W, height: H, bitsPerComponent: 8, bytesPerRow: W, space: cs, bitmapInfo: CGImageAlphaInfo.none.rawValue)!
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: W, height: H))
    }
    // color version for saturation
    var cbuf = [UInt8](repeating: 0, count: W*H*4)
    cbuf.withUnsafeMutableBytes { p in
        let ctx = CGContext(data: p.baseAddress, width: W, height: H, bitsPerComponent: 8, bytesPerRow: W*4, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        ctx.draw(img, in: CGRect(x: 0, y: 0, width: W, height: H))
    }
    let mean = Double(buf.reduce(0){ $0 + Int($1) }) / Double(buf.count)
    let white = Double(buf.filter{ $0 > 225 }.count) / Double(buf.count)
    var sat = 0.0
    for i in 0..<(W*H) {
        let r = Double(cbuf[i*4]), g = Double(cbuf[i*4+1]), b = Double(cbuf[i*4+2])
        let mx = max(r,g,b), mn = min(r,g,b)
        sat += mx > 0 ? (mx-mn)/mx : 0
    }
    sat /= Double(W*H)
    print(String(format:"%.0f,%.1f,%.3f,%.3f", t, mean, white, sat))
    t += step
}
