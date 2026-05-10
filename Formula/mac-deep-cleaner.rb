class MacDeepCleaner < Formula
  include Language::Python::Virtualenv

  desc "Professional macOS cleanup CLI with safe undo, reports, and scanners"
  homepage "https://github.com/NK2552003/Mac-Cleaner"
  url "https://files.pythonhosted.org/packages/source/m/mac-deep-cleaner/mac-deep-cleaner-1.0.0.tar.gz"
  sha256 "REPLACE_WITH_PYPI_SDIST_SHA256"
  license "MIT"

  depends_on "python@3.12"

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
    sha256 "439594978a49a09530cff7ebc4b5c7103ef57baf48d5ea3184f21d9a2befa098"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.8.tar.gz"
    sha256 "ed53c9d8990d83c2a830a063fd8edacda30827a1c8e51c9e2f88e4f1fb7c348f"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/pyyaml-6.0.2.tar.gz"
    sha256 "d584d9ec91ad65861cc08d18e14870d7ce0bbddf44738249e389a49b0d4a0d9d"
  end

  resource "packaging" do
    url "https://files.pythonhosted.org/packages/source/p/packaging/packaging-24.2.tar.gz"
    sha256 "c228a6dc5afe34dad71e0c11f0a37af6ddbfb85f1a6f9d60e03f53d92f7b12a2"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "Mac Deep Cleaner", shell_output("#{bin}/mac-cleaner --help")
    assert_match "Mac Deep Cleaner", shell_output("#{bin}/mdc --help")
    assert_match "total_bytes", shell_output("#{bin}/mdc scan --ci --threshold-mb 0")
  end
end
