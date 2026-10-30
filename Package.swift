// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MacDeepCleanerDesktop",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "mac-deep-cleaner",
            targets: ["MacDeepCleanerDesktop"]
        ),
        .executable(
            name: "app-icon-helper",
            targets: ["AppIconHelper"]
        ),
    ],
    targets: [
        .executableTarget(
            name: "MacDeepCleanerDesktop",
            path: "desktop",
            exclude: ["app_icon.swift", "make_icon.swift", "AppIcon.icns"],
            sources: ["main.swift", "window_chrome.swift"]
        ),
        .executableTarget(
            name: "AppIconHelper",
            path: "desktop",
            exclude: ["main.swift", "window_chrome.swift", "make_icon.swift", "AppIcon.icns"],
            sources: ["app_icon.swift"]
        ),
    ]
)
