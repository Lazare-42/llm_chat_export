# signal-export: PDF friendly
Export chats from the [Signal](https://www.signal.org/) [Desktop app](https://www.signal.org/download/) to Markdown and HTML files with attachments. Each chat is exported as an individual .md/.html file and the attachments for each are stored in a separate folder. Attachments are linked from the Markdown files and displayed in the HTML (pictures, videos, voice notes). This is forked from https://github.com/carderne/signal-export. 

In this fork, I have made changes to the script to ensure PDF files can properly be generated from the output. This version of this script removes all pagination present in the original, for the sake of generating PDF's. It also re-renders emoji's in the HTML-output, so that webkit renders can successfully include emoji's in the output PDF; which is not possible with the original output.

Originally adapted from https://github.com/mattsta/signal-backup.

## Example
An export for a group conversation looks as follows:
```markdown
[2019-05-29, 15:04] Me: How is everyone?
[2019-05-29, 15:10] Aya: We're great!
[2019-05-29, 15:20] Jim: I'm not.
```

Images are attached inline with `![name](path)` while other attachments (voice notes, videos, documents) are included as links like `[name](path)` so a click will take you to the file.

This is converted to HTML at the end so it can be opened with any web browser. The stylesheet `.css` is still very basic but I'll get to it sooner or later.

## Installation
First clone and install requirements (preferably into a virtualenv):
```
git clone https://github.com/liroyvh/signal-export.git
cd signal-export
pip install -r requirements.txt
```

### For Linux
Then to get sqlcipher working:
```
sudo apt install libsqlcipher-dev libssl-dev
```

Then clone [sqlcipher](https://github.com/sqlcipher/sqlcipher) and install it:
```
git clone https://github.com/sqlcipher/sqlcipher.git
cd sqlcipher
mkdir build && cd build
../configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto"
sudo make install
```

### For MacOS
- Install [Homebrew](https://brew.sh).
- Run `brew install openssl sqlcipher wkhtmltopdf`

## Usage
The following should work, and exports all your conversations to a sub-directory named "EXPORT":
```
./sigexport.py EXPORT
```

If you get an error:

    pysqlcipher3.dbapi2.DatabaseError: file is not a database

try adding the `--manual` option.

The full options are below:
```
Usage: ./sigexport.py [OPTIONS] [DEST]

Options:
  -s, --source PATH  Path to Signal config and database
      --old PATH     Path to previous export to merge with
  -c, --chats "NAME"  Comma-separated chat names to include. These are contact names or group names
  --list-chats              List all available chats/conversations
  --old PATH         Path to previous export to merge with
  -o, --overwrite    Flag to overwrite existing output
  -m, --manual       Flag to manually decrypt the database
  -v, --verbose      Enable verbose output logging
  --help             Show this message and exit.
```

Now if you want to convert all the conversations to PDF, please run the following command in your "EXPORT" folder:
```
mkdir -p pdf && find . -maxdepth 2 -name '*.html' -exec sh -c 'for f; do wkhtmltopdf --enable-local-file-access "$f" "./pdf/$(basename "$(dirname "$f")").pdf"; done' _ {} +
```
**PLEASE BE AWARE THAT THE COMMAND ABOVE TO EXPORT TO PDF HAS BEEN WRITTEN FOR MacOS**  
For Linux: please first find instructions to install wkhtmltopdf for your distribution. (Example: [Ubuntu](https://websiteforstudents.com/how-to-install-wkhtmltopdf-wkhtmltoimage-on-ubuntu-18-04-16-04/)) Then run the above command.

You can add `--source /path/to/source/dir/` if the script doesn't manage to find the Signal config location. Default locations per OS are below. The directory should contain a folder called `sql` with a `db.sqlite` inside it.
- Linux: `~/.config/Signal/`
- macOS: `~/Library/Application Support/Signal/`
- Windows: `~/AppData/Roaming/Signal/`

You can also use `--old /previously/exported/dir/` to merge the new export with a previous one. _Nothing will be overwritten!_ It will put the combined results in whatever output directory you specified and leave your previos export untouched. Exercise is left to the reader to verify that all went well before deleting the previous one.
