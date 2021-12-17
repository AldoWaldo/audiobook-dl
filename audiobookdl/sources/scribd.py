from ..utils.source import Source
from PIL import Image
import io


class ScribdSource(Source):
    match = [
        r"https?://(www)?.scribd.com/listen/\d+",
        r"https?://(www)?.scribd.com/audiobook/\d+/"
    ]
    require_cookies = True
    _original = False

    def get_title(self):
        if self._title[-5:] == ", The":
            split = self._title.split(', ')
            if len(split) == 2:
                return f"{split[1]} {split[0]}"
        return self._title

    def get_cover(self):
        # Downloading image from scribd
        raw_cover = self.get(self._cover)
        # Removing padding on the top and bottom
        if self._original:
            return raw_cover
        im = Image.open(io.BytesIO(raw_cover))
        width, height = im.size
        cropped = im.crop((0, (height-width)/2, width, width+(height-width)/2))
        cover = io.BytesIO()
        cropped.save(cover, format="jpeg")
        return cover.getvalue()

    def get_metadata(self):
        metadata = {}
        if not self._original:
            if len(self.meta["authors"]):
                metadata["author"] = "; ".join(self.meta["authors"])
            if len(self.meta["series"]):
                metadata["series"] = self.meta["series"][0]
        return metadata

    def get_files(self):
        if self._original:
            return self.get_stream_files(
                self._stream_url,
                headers={"Authorization": self._jwt})
        else:
            files = []
            for part, i in enumerate(self.media["playlist"]):
                chapter = i["chapter_number"]
                chapter_str = "0"*(3-len(str(part)))+str(part)
                files.append({
                    "url": i["url"],
                    "title": f"Chapter {chapter}",
                    "part": chapter_str,
                    "ext": "mp3"
                })
            return files

    def before(self, *args):
        if self.match_num == 1:
            book_id = self.url.split("/")[4]
            self.url = f"https://www.scribd.com/listen/{book_id}"
        user_id = self.find_in_page(
                self.url,
                r'(?<=(account_id":"scribd-))\d+')
        book_id = self.find_in_page(
                self.url,
                r'(?<=(external_id":"))(scribd_)?\d+')
        headers = {
            'Session-Key': self.find_in_page(
                self.url,
                '(?<=(session_key":"))[^"]+')
        }
        if book_id[:7] == "scribd_":
            self._original = True
            self._csrf = self.get_json(
                "https://www.scribd.com/csrf_token",
                headers={"href": self.url})
            self._jwt = self.find_in_page(
                self.url,
                r'(?<=("jwt_token":"))[^"]+')
            self._stream_url = f"https://audio.production.scribd.com/audiobooks/{book_id[7:]}/192kbps.m3u8"
            self._title = self.find_in_page(
                self.url,
                r'(?<=("title":"))[^"]+')
            self._cover = self.find_in_page(
                self.url,
                r'(?<=("cover_url":"))[^"]+')
        else:
            misc = self.get_json(
                f"https://api.findawayworld.com/v4/accounts/scribd-{user_id}/audiobooks/{book_id}",
                headers=headers,
            )
            self.meta = misc['audiobook']
            self._title = self.meta["title"]
            self._cover = self.meta["cover_url"]
            self.media = self.post_json(
                f"https://api.findawayworld.com/v4/audiobooks/{book_id}/playlists",
                headers=headers,
                json={
                    "license_id": misc['licenses'][0]['id']
                }
            )
            self.misc = misc