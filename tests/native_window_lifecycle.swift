@main
struct WindowLifecycleTests {
    static func main() {
        var normal = WindowPresentation()
        precondition(normal.requestClose() == .hide)
        normal.requestShow()
        precondition(normal.didExit() == .none)

        var fullscreen = WindowPresentation()
        fullscreen.willEnter()
        precondition(fullscreen.didEnter() == .none)
        precondition(fullscreen.requestClose() == .exitFullscreen)
        precondition(fullscreen.requestClose() == .none, "Do not toggle twice during exit")
        fullscreen.willExit()
        precondition(fullscreen.didExit() == .hide, "Hide only after leaving the Space")
        fullscreen.requestShow()
        precondition(fullscreen.phase == .windowed)
        precondition(fullscreen.didExit() == .none)

        var reopened = WindowPresentation()
        _ = reopened.didEnter()
        precondition(reopened.requestClose() == .exitFullscreen)
        reopened.requestShow()
        precondition(reopened.didExit() == .none, "Reopening must cancel delayed hiding")

        var entering = WindowPresentation()
        entering.willEnter()
        precondition(entering.requestClose() == .none)
        precondition(entering.didEnter() == .exitFullscreen)
        precondition(entering.didExit() == .hide)

        var failedEntry = WindowPresentation()
        failedEntry.willEnter()
        precondition(failedEntry.requestClose() == .none)
        precondition(failedEntry.didExit() == .hide, "A failed entry can hide safely in windowed mode")

        var reopenedDuringEntry = WindowPresentation()
        reopenedDuringEntry.willEnter()
        _ = reopenedDuringEntry.requestClose()
        reopenedDuringEntry.requestShow()
        precondition(reopenedDuringEntry.didEnter() == .none)

        var failed = WindowPresentation()
        _ = failed.didEnter()
        _ = failed.requestClose()
        precondition(failed.failedExit() == .show, "An exit failure must not strand a hidden window")
        precondition(failed.phase == .fullscreen)
        precondition(failed.requestClose() == .exitFullscreen)

        var manualExit = WindowPresentation()
        _ = manualExit.didEnter()
        manualExit.willExit()
        precondition(manualExit.requestClose() == .none)
        precondition(manualExit.didExit() == .hide)
        print("Native window lifecycle passed: normal close, fullscreen exit, reopen races, entering/exiting close, and failed exit recovery.")
    }
}
