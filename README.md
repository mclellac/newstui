# News TUI

A simple, terminal-based news reader.

## Installation

To install the application, you can use `pip` to install it directly from this repository:

```bash
pip install .
```

This will install the `newstui` command-line tool.

## Usage

Once installed, you can run the application with the following command:

```bash
newstui
```

### Options

-   `--theme <themename>`: Temporarily use a different theme.
-   `--debug`: Enable debug logging to a file in `/tmp/`.

## Configuration

The application can be configured via a `config.json` file located at `~/.config/news/config.json`.

### Themes

The application supports custom themes. A selection of themes is provided in the `config/news/themes` directory of this repository.

To use a theme, you must first copy the theme files to your user configuration directory:

```bash
mkdir -p ~/.config/news/themes
cp -r config/news/themes/* ~/.config/news/themes/
```

Then, you can specify the theme to use in your `config.json` file. For example, to use the `dracula` theme, your `~/.config/news/config.json` should look like this:

```json
{
    "theme": "dracula"
}
```

This will load the `dracula.css` theme file from your `~/.config/news/themes` directory.