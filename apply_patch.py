import pathlib

def patch_uc():
    try:
        import undetected_chromedriver
        import os
        pkg_dir = pathlib.Path(undetected_chromedriver.__file__).parent
        patch_file = pkg_dir / "patcher.py"
        content = patch_file.read_text()
        content = content.replace(
            "from distutils.version import LooseVersion",
            "from packaging.version import Version as LooseVersion"
        )
        patch_file.write_text(content)
        print("✔️ undetected_chromedriver patched successfully.")
    except Exception as e:
        print(f"❌ Could not patch undetected_chromedriver: {e}")

if __name__ == "__main__":
    patch_uc()
