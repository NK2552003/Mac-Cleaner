// Closing a fullscreen window must finish leaving its Space before hiding it.
// A reopen during that transition cancels the pending hide.
struct WindowPresentation {
    enum Phase { case windowed, entering, fullscreen, exiting }
    enum Action { case none, hide, exitFullscreen, show }
    private(set) var phase = Phase.windowed
    private var wantsHidden = false

    mutating func requestClose() -> Action {
        wantsHidden = true
        switch phase {
        case .windowed: return .hide
        case .fullscreen:
            phase = .exiting
            return .exitFullscreen
        case .entering, .exiting: return .none
        }
    }

    mutating func requestShow() { wantsHidden = false }
    mutating func willEnter() { phase = .entering }
    mutating func willExit() { phase = .exiting }
    mutating func didEnter() -> Action {
        phase = .fullscreen
        return wantsHidden ? requestClose() : .none
    }
    mutating func didExit() -> Action {
        phase = .windowed
        return wantsHidden ? .hide : .none
    }
    mutating func failedExit() -> Action {
        phase = .fullscreen
        wantsHidden = false
        return .show
    }
}
