# News TUI

A terminal-based news reader.

## Installation

```bash
pip install .
```

This will install the `newstui` command-line tool.

## Usage

To run the application:

```bash
newstui
```

### Keybindings

| Key                | Action                   |
| ------------------ | ------------------------ |
| `q`                | Quit                     |
| `r`                | Refresh                  |
| `b`                | Bookmark                 |
| `B`                | Show Bookmarks           |
| `s`                | Settings                 |
| `left` / `right`   | Navigate Panes           |
| `ctrl+p`           | Command Palette          |
| `ctrl+l`           | Toggle Sections Pane     |
| `/`                | Filter Headlines         |
| `o`                | Open in Browser (in story view) |

### Configuration

The application can be configured via a `config.json` file located at `~/.config/news/config.json`.

For advanced configuration options, such as adding custom news sources or creating meta sections, please refer to the example configuration file.