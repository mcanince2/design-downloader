# Contributing to Design Downloader

Thanks for helping improve Design Downloader! 🎉

## Development setup

```bash
git clone https://github.com/mcanince2/design-downloader.git
cd design-downloader

pip install -r requirements.txt

# Desktop app
python main_app.py

# OR: backend server for the Chrome extension
python server.py        # http://localhost:5200
```

To load the extension: open `chrome://extensions/`, enable **Developer mode**,
click **Load unpacked**, and select the `extension/` folder.

## Guidelines

- One focused change per pull request.
- When a target site changes its markup and a downloader breaks, a fix for the
  relevant `*_downloader.py` is the most valuable contribution you can send.
- **Never commit secrets.** This project needs none — keep it that way.
- Test against real Behance / Dribbble / Pinterest URLs before submitting.

## Reporting bugs / requesting features

Use the issue templates so we can reproduce and prioritize quickly.

## Code of Conduct

This project follows our [Code of Conduct](.github/CODE_OF_CONDUCT.md).
