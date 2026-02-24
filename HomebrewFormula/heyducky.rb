class HeyDucky < Formula
  desc "HeyDucky — your AI rubber duck that actually talks back"
  homepage "https://github.com/IdanG7/HeyDucky"
  url "https://github.com/IdanG7/HeyDucky/archive/refs/tags/v0.1.0.tar.gz"
  # sha256 — fill in after creating the release tarball
  sha256 ""
  license "MIT"

  depends_on "python@3.12"
  depends_on "portaudio"

  def install
    python3 = Formula["python@3.12"].opt_bin/"python3.12"
    venv = libexec/"venv"

    system python3, "-m", "venv", venv
    venv_pip = venv/"bin/pip"

    system venv_pip, "install", "--upgrade", "pip"
    system venv_pip, "install", ".[tts]"

    # Link the entry-point script into Homebrew's bin
    (bin/"ducky").write_env_script(
      venv/"bin/ducky",
      PATH: "#{Formula["portaudio"].opt_lib}:#{ENV["PATH"]}",
    )
  end

  def caveats
    <<~EOS
      To get started, run the setup wizard:
        ducky --setup

      You'll need an Anthropic API key (https://console.anthropic.com/).

      Quick usage:
        ducky                          # chat mode (current directory)
        ducky --project /path/to/code  # chat about a project
        ducky script.py                # debug a Python script
    EOS
  end

  test do
    assert_match "usage", shell_output("#{bin}/ducky --help")
  end
end
