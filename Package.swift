// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "TranslationAssistant",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .executable(name: "TranslationAssistant", targets: ["TranslationAssistant"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "TranslationAssistant",
            dependencies: [],
            path: "Sources"
        )
    ]
)
