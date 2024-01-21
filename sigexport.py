#!/usr/bin/env python3

import json
import sys
import os
import shutil
from pathlib import Path
from datetime import datetime
from babel.dates import format_datetime
import re
import locale

import click
import markdown
import uuid
from bs4 import BeautifulSoup
from get_data import fetch_data, filter_data


log = False

# Set the locale to French
try:
    locale.setlocale(locale.LC_TIME, "fr_FR")
except locale.Error:
    print("French locale not supported")

def source_location():
    """Get OS-dependent source location."""

    home = Path.home()
    if sys.platform == "linux" or sys.platform == "linux2":
        source_path = home / ".config/Signal"
    elif sys.platform == "darwin":
        source_path = home / "Library/Application Support/Signal"
    elif sys.platform == "win32":
        source_path = home / "AppData/Roaming/Signal"
    else:
        print("Please manually enter Signal location using --source.")
        sys.exit(1)

    return source_path


def copy_attachments(src, dest, conversations, contacts):
    """Copy attachments and reorganise in destination directory."""

    src_att = Path(src) / "attachments.noindex"
    dest = Path(dest)

    for key, messages in conversations.items():
        name = contacts[key]["name"]
        if log:
            print(f"\tCopying attachments for: {name}")
        # some contact names are None
        if name is None:
            name = "None"
        contact_path = dest / name / "media"
        contact_path.mkdir(exist_ok=True, parents=True)
        for msg in messages:
            try:
                attachments = msg["attachments"]
                if attachments:
                    date = datetime.fromtimestamp(msg["timestamp"] / 1000.0).strftime(
                        "%Y-%m-%d"
                    )
                    for i, att in enumerate(attachments):
                        try:
                            att[
                                "fileName"
                            ] = f"{date}_{i:02}_{att['fileName']}".replace(
                                " ", "_"
                            ).replace(
                                "/", "-"
                            )
                            # account for erroneous backslash in path
                            att_path = str(att["path"]).replace("\\", "/")
                            shutil.copy2(
                                src_att / att_path, contact_path / att["fileName"]
                            )
                        except KeyError:
                            if log:
                                print(
                                    f"\t\tBroken attachment:\t{name}\t{att['fileName']}"
                                )
                        except FileNotFoundError:
                            if log:
                                print(
                                    f"\t\tAttachment not found:\t{name} {att['fileName']}"
                                )
            except KeyError:
                if log:
                    print(f"\t\tNo attachments for a message: {name}")


def make_simple(dest, conversations, contacts):
    """Output each conversation into a simple text file."""

    dest = Path(dest)
    for key, messages in conversations.items():
        name = contacts[key]["name"]
        if log:
            print(f"\tDoing markdown for: {name}")
        is_group = contacts[key]["is_group"]
        # some contact names are None
        if name is None:
            name = "None"
        mdfile = open(dest / name / "index.md", "a")

        for msg in messages:
            timestamp = (
                msg["timestamp"]
                if "timestamp" in msg
                else msg["sent_at"]
                if "sent_at" in msg
                else None
            )

            if timestamp is None:
                if log:
                    print("\t\tNo timestamp or sent_at; date set to 1970")
                date = datetime(year=1970, month=1, day=1)
            else:
                date = datetime.fromtimestamp(timestamp / 1000.0)

            date_str = date.strftime("%Y-%m-%d %H:%M")
            
            ## do NOT translate when writing to file
            ##date_str = date.strftime("%d %B %Y")

            if log:
                print(f"\t\tDoing {name}, msg: {date_str}")

            try:
                body = msg["body"]
            except KeyError:
                if log:
                    print(f"\t\tNo body:\t\t{date_str}")
                body = ""
            if body is None:
                body = ""
            body = body.replace("`", "")  # stop md code sections forming
            body += "  "  # so that markdown newlines

            sender = "No-Sender"
            if "type" in msg.keys() and msg["type"] == "outgoing":
                sender = "Me"
            else:
                try:
                    if is_group:
                        for c in contacts.values():
                            num = c["number"]
                            if num is not None and num == msg["source"]:
                                sender = c["name"]
                    else:
                        sender = contacts[msg["conversationId"]]["name"]
                except KeyError:
                    if log:
                        print(f"\t\tNo sender:\t\t{date_str}")

            try:
                attachments = msg["attachments"]
                for att in attachments:
                    file_name = att["fileName"]
                    # some file names are None
                    if file_name is None:
                        print('File name is none. You have an issue with data creation')
                        exit()
                    path = Path("media") / file_name
                    path = Path(str(path).replace(" ", "%20"))
                    if path.suffix and path.suffix.split(".")[1] in [
                        "png",
                        "jpg",
                        "jpeg",
                        "gif",
                        "tif",
                        "tiff",
                    ]:
                        body += "!"
                    body += f"[{file_name}](./{path})  "
                print(f"[{date_str}] {sender}: {body}", file=mdfile)
            except KeyError:
                if log:
                    print(f"\t\tNo attachments for a message: {name}, {date_str}")



def fix_names(contacts):
    """Remove non-filesystem-friendly characters from names."""

    for key, item in contacts.items():
        contact_name = item["number"] if item["name"] is None else item["name"]
        if contacts[key]["name"] is not None:
            contacts[key]["name"] = ''.join(x for x in contact_name if x.isalnum() or x.isspace())


    return contacts


def create_html(dest, msgs_per_page=100):
    root = Path(__file__).resolve().parents[0]
    css_source = root / "style.css"
    css_dest = dest / "style.css"
    if os.path.isfile(css_source):
        shutil.copy2(css_source, css_dest)
    else:
        print(
            f"Stylesheet ({css_source}) not found."
            f"You might want to install one manually at {css_dest}."
        )

    md = markdown.Markdown()

    for sub in dest.iterdir():
        if sub.is_dir():
            name = sub.stem
            if log:
                print(f"\tDoing html for {name}")
            path = sub / "index.md"
            # touch first
            open(path, "a")
            with path.open() as f:
                lines = f.readlines()
            lines = lines_to_msgs(lines)
            last_page = int(len(lines) / msgs_per_page)
            htfile = open(sub / "index.html", "w")
            print(
                "<!doctype html>"
                "<html lang='en'><head>"
                "<meta charset='utf-8'>"
                f"<title>{name}</title>"
                "<link rel=stylesheet href='../style.css'>"
                "</head>"
                "<body>"
                "<style>"
                "img.emoji {"
                "height: 1em;"
                "width: 1em;"
                "margin: 0 .05em 0 .1em;"
                "vertical-align: -0.1em;"
                "}"
                "</style>"
                "<script src='https://cdn.jsdelivr.net/npm/twemoji@14.0.2/dist/twemoji.min.js?11.2'></script>"
                "<script>window.onload = function () { twemoji.parse(document.body);}</script>",
                file=htfile,
            )

            page_num = 0
            for i, msg in enumerate(lines):
                if i % msgs_per_page == 0:
                    nav = ""
                    if i > 0:
                        nav += "&nbsp;"
                    nav += f"&nbsp;"
                    nav += "&nbsp;"
                    nav += "&nbsp;"
                    if page_num != 0:
                        nav += f"&nbsp;"
                    else:
                        nav += "&nbsp;"
                    nav += "</div><div class=next>"
                    if page_num != last_page:
                        nav += f"&nbsp;"
                    else:
                        nav += "&nbsp;"
                    nav += "</div></nav>"
                    print(nav, file=htfile)
                    page_num += 1

                date, sender, body = msg
                sender = sender[1:-1]
                date, time = date[1:-1].replace(",", "").split(" ")


                
                body = md.convert(body)

                # links
                p = r"(https{0,1}://\S*)"
                template = r"<a href='\1' target='_blank'>\1</a> "
                body = re.sub(p, template, body)

                # images
                soup = BeautifulSoup(body, "html.parser")

                # images
                imgs = soup.find_all("img")
                # Create a container for images if there are images
                if imgs:
                    img_grid_container = soup.new_tag('div', **{'class': 'img-grid'})

                for im in imgs:
                    if im.get("src"):
                        temp = BeautifulSoup(figure_template, "html.parser")
                        src = im["src"]
                        temp.figure.label.img["src"] = src
                        alt = im["alt"]
                        temp.figure.label.img["alt"] = alt
                        temp.figure.input["id"] = alt
                        temp.figure.label["for"] = alt
        
                        #  Add the figure to the img-grid container
                        img_grid_container.append(temp.figure)

                # Replace old images with new img-grid container
                for im in imgs:
                    im.replace_with(img_grid_container)
                    # voice notes
                    voices = soup.select(r"a[href*=\.m4a]")

                # voice notes
                voices = soup.select(r"a[href*=\.m4a]")
                for v in voices:
                    href = v["href"]
                    temp = BeautifulSoup(audio_template, "html.parser")
                    temp.audio.source["src"] = href
                    v.replace_with(temp)

                # videos
                videos = soup.select(r"a[href*=\.mp4]")
                for v in videos:
                    href = v["href"]
                    temp = BeautifulSoup(video_template, "html.parser")
                    temp.video.source["src"] = href
                    v.replace_with(temp)

                cl = "msg me" if sender == "Me" else "msg"
                print(
                    f"<div class='{cl}'><span class=date>{date}</span>"
                    f"<span class=time>{time}</span>",
                    f"<span class=sender>{sender}</span>"
                    f"<span class=body>{soup.prettify()}</span></div>",
                    file=htfile,
                )
            print("</div>", file=htfile)
            print(
                "<script>if (!document.location.hash){"
                "document.location.hash = 'pg0';}</script>",
                file=htfile,
            )
            print("</body></html>", file=htfile)


video_template = """
<video controls>
    <source src="src" type="video/mp4">
    </source>
</video>
"""

audio_template = """
<audio controls>
<source src="src" type="audio/mp4">
</audio>
"""

figure_template = """
<figure>
    <label for="src">
        <img load="lazy" src="src" alt="img">
    </label>
    <input class="modal-state" id="src" type="checkbox">
    <div class="modal">
        <label for="src">
            <div class="modal-content">
                <img class="modal-photo" loading="lazy" src="src" alt="img">
            </div>
        </label>
    </div>
</figure>
"""


def lines_to_msgs(lines):
    p = re.compile(r"^(\[\d{4}-\d{2}-\d{2},{0,1} \d{2}:\d{2}\])(.*?:)(.*\n)")
    msgs = []
    for li in lines:
        m = p.match(li)
        if m:
            msgs.append(list(m.groups()))
        else:
            msgs[-1][-1] += li
    return msgs


def merge_attachments(media_new, media_old):
    for f in media_old.iterdir():
        if f.is_file():
            shutil.copy2(f, media_new)


def merge_chat(path_new, path_old):
    with path_old.open() as f:
        old = f.readlines()
    with path_new.open() as f:
        new = f.readlines()

    try:
        a, b, c, d = old[0][:30], old[-1][:30], new[0][:30], new[-1][:30]
        if log:
            print(f"\t\tFirst line old:\t{a}")
            print(f"\t\tLast line old:\t{b}")
            print(f"\t\tFirst line new:\t{c}")
            print(f"\t\tLast line new:\t{d}")
    except IndexError:
        if log:
            print("\t\tNo new messages for this conversation")
        return

    old = lines_to_msgs(old)
    new = lines_to_msgs(new)

    merged = old + new
    merged = [m[0] + m[1] + m[2] for m in merged]
    merged = list(dict.fromkeys(merged))

    with path_new.open("w") as f:
        f.writelines(merged)


def merge_with_old(dest, old):
    for sub in dest.iterdir():
        if sub.is_dir():
            name = sub.stem
            if log:
                print(f"\tMerging {name}")
            dir_old = old / name
            if dir_old.is_dir():
                merge_attachments(sub / "media", dir_old / "media")
                path_new = sub / "index.md"
                path_old = dir_old / "index.md"
                try:
                    merge_chat(path_new, path_old)
                except FileNotFoundError:
                    if log:
                        print(f"\tNo old for {name}")
                print()


@click.command()
@click.argument("dest", type=click.Path(), default="output")
@click.option(
    "--source", "-s", type=click.Path(), help="Path to Signal source and database"
)
@click.option(
    "--chats",
    "-c",
    help="Comma-separated chat names to include. These are contact names or group names",
)
@click.option(
    "--list-chats",
    is_flag=True,
    default=False,
    help="List all available chats/conversations and then quit",
)
@click.option("--old", type=click.Path(), help="Path to previous export to merge with")
@click.option(
    "--overwrite",
    "-o",
    is_flag=True,
    default=False,
    help="Flag to overwrite existing output",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output logging",
)
@click.option(
    "--manual",
    "-m",
    is_flag=True,
    default=False,
    help="Whether to manually decrypt the db",
)
@click.option(
    "--conversation-id",
    "-i",
    help="Identifier of the conversation to be exported",
)
@click.option(
    "--year",
    "-y",
    type=int,
    default=None,
    help="Only include messages from this year (e.g., 2023)."
)
@click.option(
    "--attachments-only",
    is_flag=True,
    help="Only include messages with attachments."
)

def main(
    dest,
    old=None,
    source=None,
    overwrite=False,
    verbose=False,
    manual=False,
    chats=None,
    list_chats=None,
    conversation_id=None,
    year=None,
    attachments_only=False,
):
    """
    Read the Signal directory and output attachments and chat files to DEST directory.
    Assumes the following default directories, can be overridden wtih --source.

    Default for DEST is a sub-directory output/ in the current directory.

    \b
    Default Signal directories:
     - Linux: ~/.config/Signal
     - macOS: ~/Library/Application Support/Signal
     - Windows: ~/AppData/Roaming/Signal
    """

    global log
    log = verbose

    if source:
        src = Path(source)
    else:
        src = source_location()
    source = src / "config.json"
    db_file = src / "sql" / "db.sqlite"

    if chats:
        chats = chats.split(",")

    # Read sqlcipher key from Signal config file
    if source.is_file():
        with open(source, "r") as conf:
            key = json.loads(conf.read())["key"]
    else:
        print(f"Error: {source} not found in directory {src}")
        sys.exit(1)

    if log:
        print(f"\nFetching data from {db_file}\n")
    convos, contacts = fetch_data(db_file, key, manual=manual, chats=chats, conversation_id=conversation_id, log=log)
    convos, contacts = filter_data(convos, contacts, year, attachments_only, log=log)

    # ... existing code ...

    if list_chats:
        names = sorted(v["name"] for v in contacts.values() if v["name"] is not None)
        print("\n".join(names))
        sys.exit()

    dest = Path(dest).expanduser()
    if not dest.is_dir():
        dest.mkdir(parents=True)
    elif overwrite:
        shutil.rmtree(dest)
        dest.mkdir(parents=True)
    else:
        print(f"Output folder '{dest}' already exists, didn't do anything!")
        print("Use --overwrite to ignore existing directory.")
        sys.exit(1)

    contacts = fix_names(contacts)
    print("\nCopying and renaming attachments")
    copy_attachments(src, dest, convos, contacts)
    print("\nCreating markdown files")
    make_simple(dest, convos, contacts)
    if old:
        print(f"\nMerging old at {old} into output directory")
        print("No existing files will be deleted or overwritten!")
        merge_with_old(dest, Path(old))
    print("\nCreating HTML files")
    create_html(dest)

    print(f"\nDone! Files exported to {dest}.\n")


if __name__ == "__main__":
    main()
