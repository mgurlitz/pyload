#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import tempfile
from time import time
from base64 import b64decode
import hashlib

from module.Plugin import Plugin

class ShareonlineBiz(Plugin):

    def __init__(self, parent):
        Plugin.__init__(self, parent)
        props = {}
        props['name'] = "ShareonlineBiz"
        props['type'] = "hoster"
        props['pattern'] = r"(?:http://)?(?:www.)?share-online.biz/download.php\?id="
        props['version'] = "0.1"
        props['description'] = """Shareonline.biz Download Plugin"""
        props['author_name'] = ("spoob")
        props['author_mail'] = ("spoob@pyload.org")
        self.props = props
        self.parent = parent
        self.html = [None, None]
        self.want_reconnect = False
        self.init_ocr()
        self.url = self.parent.url
        self.read_config()
        if self.config['premium']:
            self.multi_dl = True
        else:
            self.multi_dl = False

    def prepare(self, thread):
        pyfile = self.parent

        self.download_api_data()
        if self.api_data["status"]:
            self.download_html()
            pyfile.status.filename = self.api_data["filename"]
            pyfile.status.waituntil = self.time_plus_wait
            pyfile.status.url = self.get_file_url()
            pyfile.status.want_reconnect = self.want_reconnect
        else:
            raise Exception, "File not found"
            return False

    def download_api_data(self):
        """
        http://images.rapidshare.com/apidoc.txt
        """
        api_url_base = "http://www.share-online.biz/linkcheck/linkcheck.php?md5=1"
        api_param_file = {"links": self.url}
        src = self.req.load(api_url_base, cookies=False, post=api_param_file)

        fields = src.split(";")
        self.api_data = {}
        self.api_data["fileid"] = fields[0]
        self.api_data["status"] = fields[1]
        if self.api_data["status"] == "NOTFOUND":
            return
        self.api_data["filename"] = fields[2]
        self.api_data["size"] = fields[3] # in bytes
        self.api_data["checksum"] = fields[4].strip().lower().replace("\n\n", "") # md5        

    def download_html(self):
        if self.config['premium']:
            post_vars = {"act": "login",
                         "location": "service.php",
                         "dieseid": "",
                         "user": self.config['username'],
                         "pass": self.config['password'],
                         "login":"Log+me+in",
                         "folder_autologin":"1"}
            self.req.load("http://www.share-online.biz/login.php", cookies=True, post=post_vars)
        url = self.parent.url
        self.html[0] = self.req.load(url, cookies=True)
        
        if not self.config['premium']:
            captcha_image = tempfile.NamedTemporaryFile(suffix=".jpg").name

            for i in range(10):
                self.req.download("http://www.share-online.biz/captcha.php", captcha_image, cookies=True)
                captcha = self.ocr.get_captcha(captcha_image)
                self.logger.debug("Captcha %s: %s" % (i, captcha))
                self.html[1] = self.req.load(url, post={"captchacode": captcha}, cookies=True)
                if re.search(r"Der Download ist Ihnen zu langsam", self.html[1]) != None:
                    self.time_plus_wait = time() + 15
                    break

            os.remove(captcha_image)

    def get_file_url(self):
        """ returns the absolute downloadable filepath
        """
        if not self.want_reconnect:
            file_url_pattern = 'loadfilelink\.decode\("(.*)\); document'
            return b64decode(re.search(file_url_pattern, self.html[1]).group(1))
        else:
            return False

    def check_file(self, local_file):
        if self.api_data and self.api_data["checksum"]:
            h = hashlib.md5()
            f = open(local_file, "rb")
            h.update(f.read())
            f.close()
            hexd = h.hexdigest()
            if hexd == self.api_data["checksum"]:
                return (True, 0)
            else:
                return (False, 1)
        else:
            return (True, 5)