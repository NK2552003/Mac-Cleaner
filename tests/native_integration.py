"""Interactive macOS acceptance: real AppKit chrome, close, Dock policy and reopen.

Builds a temporary signed shell around disposable browser fixtures. It never scans
or cleans the host. Run from an unlocked desktop session; no notification permission
is requested. Native banner delivery still needs manual permission/Focus acceptance.
"""
import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = r'''
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        guard let url = webView.url, url.host == "127.0.0.1", url.port == origin?.port else { return }
        webView.callAsyncJavaScript("while (typeof ready === 'undefined' || !ready) await new Promise(r => setTimeout(r,100)); await api('/api/settings', {theme:'light'}); applyTheme('light'); navigate('settings');", arguments: [:], in: nil, in: .page) { result in
            if case .failure(let error) = result { fatalError(error.localizedDescription) }
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) {
                precondition(NSApp.activationPolicy() == .regular)
                precondition(self.chrome.isLight)
                let color = self.window.backgroundColor.usingColorSpace(.sRGB)!
                precondition(abs(color.redComponent - 238.0/255) < 0.001)
                precondition(abs(color.greenComponent - 241.0/255) < 0.001)
                precondition(abs(color.blueComponent - 245.0/255) < 0.001)
                self.window.performClose(nil)
                precondition(!self.window.isVisible)
                precondition(NSApp.activationPolicy() == .accessory)
                precondition(self.statusItem != nil)
                self.showWorkspace()
                precondition(self.window.isVisible)
                precondition(NSApp.activationPolicy() == .regular)
                let file = ProcessInfo.processInfo.environment["MDC_NATIVE_RESULT"]!
                try! "PASS: native light chrome, real window close, accessory Dock policy, status item retained, reopen regular policy\n".write(toFile:file, atomically:true, encoding:.utf8)
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }
            }
        }
    }
'''


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Requires an unlocked macOS desktop.')
    with tempfile.TemporaryDirectory(prefix='mdc-native-acceptance-') as directory:
        work = Path(directory)
        app = work / 'MDC Native Acceptance.app'
        contents = app / 'Contents'
        resources = contents / 'Resources'
        (contents / 'MacOS').mkdir(parents=True)
        (resources / 'engine').mkdir(parents=True)
        source = (ROOT / 'desktop/main.swift').read_text()
        source = source.replace('    func applicationWillTerminate(', HOOK + '\n    func applicationWillTerminate(', 1)
        main_swift = work / 'main.swift'
        main_swift.write_text(source)
        # Absolute interpreter and repository paths only; the wrapper serves fixtures.
        engine = resources / 'engine/mac-deep-cleaner-engine'
        engine.write_text('#!' + sys.executable + '\nimport runpy,sys\nsys.path.insert(0,' + repr(str(ROOT / 'tests')) + ')\nrunpy.run_path(' + repr(str(ROOT / 'tests/workspace_fixture.py')) + ',run_name="__main__")\n')
        engine.chmod(0o755)
        with (contents / 'Info.plist').open('wb') as handle:
            plistlib.dump({'CFBundleIdentifier':'com.macdeepcleaner.acceptance','CFBundleName':'MDC Native Acceptance',
                          'CFBundleExecutable':'mac-deep-cleaner','CFBundlePackageType':'APPL',
                          'NSAppTransportSecurity':{'NSAllowsLocalNetworking':True}}, handle)
        subprocess.run(['xcrun','swiftc',str(main_swift),str(ROOT / 'desktop/window_chrome.swift'),
                        str(ROOT / 'desktop/window_presentation.swift'),'-o',str(contents / 'MacOS/mac-deep-cleaner')],check=True)
        subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True,capture_output=True)
        result = work / 'result.txt'
        process = subprocess.Popen([str(contents / 'MacOS/mac-deep-cleaner')], env={**os.environ,'MDC_NATIVE_RESULT':str(result)})
        try:
            process.wait(timeout=40)
            if process.returncode or not result.exists():
                raise SystemExit('Native acceptance failed.')
            print(result.read_text())
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()
