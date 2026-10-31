class MacDeepCleaner < Formula
  include Language::Python::Virtualenv

  desc "Local Mac cleanup, maintenance, and external-disk management"
  homepage "https://github.com/NK2552003/Mac-Cleaner"
  url "https://files.pythonhosted.org/packages/source/m/mac-deep-cleaner/mac_deep_cleaner-3.2.0.tar.gz"
  sha256 "NONE_FOR_NOW"
  license "Apache-2.0"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "mac-deep-cleaner 3.2.0", shell_output("#{bin}/mac-deep-cleaner --version")
    assert_match "mac-deep-cleaner 3.2.0", shell_output("#{bin}/mac-cleaner --version")
    assert_match "mac-deep-cleaner 3.2.0", shell_output("#{bin}/mdc --version")
  end
end
