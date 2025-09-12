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

### News Sources

The application can be configured to use different news sources. The default news source is CBC News. You can change the news source by adding a `source` key to your `config.json` file. The available sources are `cbc` and `rss`.

#### RSS

To use an RSS feed as your news source, you need to configure the `rss` source in your `config.json` file. The `rss` source takes a `feeds` dictionary, where the keys are the names of the feeds and the values are the URLs of the feeds.

Here is an example `config.json` file that uses the `rss` source with two feeds:

```json
{
    "theme": "dracula",
    "source": "rss",
    "sources": {
        "rss": {
            "feeds": {
                "Hacker News": "https://news.ycombinator.com/rss",
                "Lobsters": "https://lobste.rs/rss"
            }
        }
    }
}
```