import base64
import json
import time
from io import BytesIO
import requests
import rsa
from urllib import parse
import hashlib
from typing import List


class BilibiliClient:
    APP_KEY = "bca7e84c2d947ac6"
    SEND_WITH_IMG_URL = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/create_draw"
    SEND_TEXT_ONLY_URL = "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/create"
    UPLOAD_IMG_URL = "https://api.vc.bilibili.com/api/v1/drawImage/upload"

    def __init__(self, user_name: str = None, password: str = None):
        self._session = requests.Session()
        self._session.headers.update({"Referer": "https://www.bilibili.com", "User-Agent": "Mozilla/5.0"})

        self.username, self.password = user_name, password
        self.access_token: str = ''
        self.refresh_token: str = ''

        # these 2 are used to hold the stuff to be sent
        self.dynamic_text = ''
        self.dynamic_img_list: List[BytesIO] = []

        if self.username and self.password:
            self.login()  # login with password on object creation
        # else __init__.py should set the cookies

    def clear(self):
        """
        clears stored stuff like dynamic_text and dynamic_img_list
        It doesn't clear itself after sending, but relies on the driver code (bot) to call clear on the object when needed
        """
        self.dynamic_text = ''
        self.dynamic_img_list = []

    @staticmethod
    def calc_sign(param):
        salt = "60698ba2f68e01ce44738920a0ffe768"
        sign_hash = hashlib.md5()
        sign_hash.update(f"{param}{salt}".encode())
        return sign_hash.hexdigest()

    def _solve_captcha(self, image):
        url = "https://bili.dev:2233/captcha"
        payload = {'image': base64.b64encode(image).decode("utf-8")}
        response = self._session.post(url, json=payload).json()
        return response['message'] if response and response.get("code") == 0 else None

    def login(self):
        def get_key():
            url = "https://passport.bilibili.com/api/oauth2/getKey"
            payload = {
                'appkey': self.APP_KEY,
                'sign'  : self.calc_sign(f"appkey={self.APP_KEY}"),
            }
            response = self._session.post(url, data=payload).json()
            if response and response.get("code") == 0:
                return {
                    'key_hash': response['data']['hash'],
                    'pub_key' : rsa.PublicKey.load_pkcs1_openssl_pem(response['data']['key'].encode()),
                }

        key = get_key()
        key_hash, pub_key = key['key_hash'], key['pub_key']
        url = "https://passport.bilibili.com/api/v2/oauth2/login"
        param = f"appkey={self.APP_KEY}" \
                f"&password={parse.quote_plus(base64.b64encode(rsa.encrypt(f'{key_hash}{self.password}'.encode(), pub_key)))}" \
                f"&username={parse.quote_plus(self.username)}"
        payload = f"{param}&sign={self.calc_sign(param)}"
        headers = {'Content-type': "application/x-www-form-urlencoded"}
        response = self._session.post(url, data=payload, headers=headers).json()

        if response and response.get("code") is not None:
            if response['code'] == -105:
                url = "https://passport.bilibili.com/captcha"
                headers = {'Host': "passport.bilibili.com"}
                response = self._session.get(url, headers=headers).content
                captcha = self._solve_captcha(response)
                if captcha:
                    print(f"登录验证码识别结果: {captcha}")
                    key = get_key()
                    key_hash, pub_key = key['key_hash'], key['pub_key']
                    url = "https://passport.bilibili.com/api/v2/oauth2/login"
                    param = f"appkey={self.APP_KEY}&captcha={captcha}" \
                            f"&password={parse.quote_plus(base64.b64encode(rsa.encrypt(f'{key_hash}{self.password}'.encode(), pub_key)))}" \
                            f"&username={parse.quote_plus(self.username)}"
                    payload = f"{param}&sign={self.calc_sign(param)}"
                    headers = {'Content-type': "application/x-www-form-urlencoded"}
                    response = self._session.post(url, data=payload, headers=headers)
                    print('captcha finished with text:', response.text)
                else:
                    print('captcha service unavailable')

            elif response['code'] == -449:
                print("服务繁忙, 尝试使用V3接口登录")
                url = "https://passport.bilibili.com/api/v3/oauth2/login"
                param = f"access_key=&actionKey=appkey&appkey={self.APP_KEY}&build=6040500" \
                        f"&captcha=&challenge=&channel=bili&cookies=&device=phone&mobi_app=android" \
                        f"&password={parse.quote_plus(base64.b64encode(rsa.encrypt(f'{key_hash}{self.password}'.encode(), pub_key)))}" \
                        f"&permission=ALL&platform=android&seccode=&subid=1&ts={int(time.time())}" \
                        f"&username={parse.quote_plus(self.username)}&validate="
                payload = f"{param}&sign={self.calc_sign(param)}"
                headers = {'Content-type': "application/x-www-form-urlencoded"}
                response = self._session.post(url, data=payload, headers=headers).json()
                print('got code -449, using v3 api, response text:', response)

                for cookie in response['data']['cookie_info']['cookies']:
                    self._session.cookies.set(cookie['name'], cookie['value'], domain=".bilibili.com")
                self.access_token = response['data']['token_info']['access_token']
                self.refresh_token = response['data']['token_info']['refresh_token']

            elif response['code'] == 0 and response['data']['status'] == 0:
                print('login successful with json response:', response)
                for cookie in response['data']['cookie_info']['cookies']:
                    self._session.cookies.set(cookie['name'], cookie['value'], domain=".bilibili.com")
                self.access_token = response['data']['token_info']['access_token']
                self.refresh_token = response['data']['token_info']['refresh_token']
                print("登录成功")
                return True

            else:
                print('login failed with unexpected response code:', response)
        else:
            print('login failed, no response code:', response)

    def get_image(self, url: str) -> bool:
        """
        Use http request to get the image from the url and store it as bytes.
        :return operation successful or not
        """
        try:
            img_bytes = BytesIO(requests.get(url).content)
        except:
            return False
        self.dynamic_img_list.append(img_bytes)
        return True

    # DON'T call this, unless login by password works again, which sets the tokens
    def refresh(self):
        url = "https://passport.bilibili.com/api/v2/oauth2/refresh_token"
        param = f"access_key={self.access_token}&appkey={self.APP_KEY}&refresh_token={self.refresh_token}&ts={int(time.time())}"
        payload = f"{param}&sign={self.calc_sign(param)}"
        headers = {'Content-type': "application/x-www-form-urlencoded"}
        response = self._session.post(url, data=payload, headers=headers).json()
        print('response from refresh token post request', response)
        if response and response.get("code") == 0:
            # also records the new response in the file
            with open('bilibili.txt', 'w') as fp:
                fp.write(json.dumps(response))

            for cookie in response['data']['cookie_info']['cookies']:
                self._session.cookies.set(cookie['name'], cookie['value'], domain=".bilibili.com")
            self.access_token = response['data']['token_info']['access_token']
            self.refresh_token = response['data']['token_info']['refresh_token']

    def send_dynamic(self):
        """Sends a bilibili dynamic (dong tai) with the received text/images, doesn't handle at's (i.e. @someone)"""
        def get_text_dynamic_payload():
            """
            不解析并忽略@人数据

            :return: 纯文本动态POST payload
            """
            data = {
                "dynamic_id": 0,
                "type"      : 4,
                "rid"       : 0,
                "content"   : self.dynamic_text.strip(),
                "extension" : "{\"emoji_type\":1}",
                "at_uids"   : "",
                "ctrl"      : "",
                "csrf": self._session.cookies.get('bili_jct'),
                "csrf_token": self._session.cookies.get('bili_jct')
            }
            return data

        def get_img_dynamic_payload():
            """
            不解析并忽略@人数据

            :return: 带图片和文字动态的POST payload
            """
            def upload_image(img_bytes: BytesIO):
                """
                uploads the image (as bytes) to bilibili

                :return: api response json data
                """
                form_data = {
                    "biz"     : "draw",
                    "category": "daily",
                    "csrf": self._session.cookies.get('bili_jct'),
                    "csrf_token": self._session.cookies.get('bili_jct')
                }
                response = self._session.post(self.UPLOAD_IMG_URL, data=form_data, files={'file_up': img_bytes}).json()
                print('response from upload image:', response)
                if response['code'] != 0:
                    print('upload image response:', response)
                    raise RuntimeError(response)
                return response['data']

            def extract_infos(img_info):
                """extract some of the response needed for posting dynamic"""
                print('response from uploading image:', img_info)
                return {"img_src": img_info["image_url"], "img_width": img_info["image_width"], "img_height": img_info["image_height"]}

            img_responses = []
            for img in self.dynamic_img_list:
                info = upload_image(img)
                img_responses.append(info)

            img_infos = list(map(extract_infos, img_responses))
            data = {
                "biz"              : 3,
                "category"         : 3,
                "type"             : 0,
                "pictures"         : json.dumps(img_infos),
                "title"            : "",
                "tags"             : "",
                "description"      : self.dynamic_text.strip(),
                "content"          : self.dynamic_text.strip(),
                "from"             : "create.dynamic.web",
                "up_choose_comment": 0,
                "extension"        : json.dumps({"emoji_type": 1, "from": {"emoji_type": 1}, "flag_cfg": {}}),
                "at_uids"          : '',
                "at_control"       : '',
                "setting"          : json.dumps({
                    "copy_forbidden": 0,
                    "cachedTime"    : 0
                }),
                "csrf"      : self._session.cookies.get('bili_jct'),
                "csrf_token": self._session.cookies.get('bili_jct')
            }
            return data

        if len(self.dynamic_img_list) == 0:  # no images, text only
            if len(self.dynamic_text) == 0:  # nothing to send
                raise RuntimeError('无可发送消息内容，图片文字均为空')
            payload = get_text_dynamic_payload()
            response = self._session.post(self.SEND_TEXT_ONLY_URL, data=payload)
            print('response from sending pure text dynamic', response.text)

        else:  # has images
            self.dynamic_img_list = self.dynamic_img_list[:9]  # allow max 9 images
            payload = get_img_dynamic_payload()
            response = self._session.post(self.SEND_WITH_IMG_URL, data=payload)
            print('response from sending img dynamic', response.text)
