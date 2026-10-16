import Foundation
import AVFoundation
import CoreImage
import AppKit

let args = CommandLine.arguments
guard args.count >= 4 else { print("usage: grab <mp4> <outdir> <sec> [sec...]"); exit(1) }
let url = URL(fileURLWithPath: args[1])
let outdir = args[2]
let asset = AVURLAsset(url: url)
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = CMTime(seconds: 0.5, preferredTimescale: 600)
gen.requestedTimeToleranceAfter  = CMTime(seconds: 0.5, preferredTimescale: 600)
gen.maximumSize = CGSize(width: 1280, height: 720)
for s in args[3...] {
    guard let sec = Double(s) else { continue }
    do {
        let img = try gen.copyCGImage(at: CMTime(seconds: sec, preferredTimescale: 600), actualTime: nil)
        let rep = NSBitmapImageRep(cgImage: img)
        let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.7])!
        let name = String(format: "%@/t%06d.jpg", outdir, Int(sec))
        try data.write(to: URL(fileURLWithPath: name))
        print("ok \(Int(sec))")
    } catch { print("fail \(s): \(error.localizedDescription)") }
}
