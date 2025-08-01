import os
import re
import json
import requests
from fnmatch import fnmatch

class ImageMarkdownSync:
    IMGPATTERN = r'!\[.*?\]\((.*?)\)|<img.*?src\ *=\ *[\'\"](.*?)[\'\"].*?>'

    def __init__(self, img_dir, md_dir, upload_client: 'SMMSClient', config_path='config.json'):
        self.img_dir = os.path.abspath(img_dir)
        self.md_dir = os.path.abspath(md_dir)
        self.config_path = config_path
        self.config = self.load_config()
        self.upload_client = upload_client

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                if os.path.getsize(self.config_path) == 0:
                    return {}
                return json.load(f)
        return {}

    def save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def upload_image(self, image_path):
        print(f"Uploading: {image_path}")
        return self.upload_client.upload(image_path)

    def sync_images(self):
        """
        Scans self.img_dir recursively, uploads missing images, and updates the config with relative paths.
        """
        img_dir_abs = os.path.dirname(os.path.abspath(self.img_dir))
        for root, _, files in os.walk(self.img_dir):
            for fname in files:
                if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                    abs_path = os.path.abspath(os.path.join(root, fname))
                    rel_path = '/' + os.path.relpath(abs_path, img_dir_abs).replace("\\", "/")
                    if rel_path not in self.config:
                        url = self.upload_image(abs_path)
                        self.config[rel_path] = url
        self.save_config()
        self.config = self.load_config()
        print(f"Image config updated: {self.config_path}")

    def get_all_md_files(self):
        md_files = []
        for path, _, files in os.walk(self.md_dir):
            for name in files:
                if fnmatch(name, "*.md"):
                    md_files.append(os.path.join(path, name))
        return md_files

    def replace_img_urls_in_md(self, file_name):
        with open(file_name, 'r', encoding='utf-8') as file:
            content = file.readlines()

        new_content = ""
        replace = False
        for line in content:
            urls = re.findall(self.IMGPATTERN, line)
            urls = [item for t in urls for item in t if item]
            for url in urls:
                if len(url) != 0 and not url.startswith('http'):
                    if url in self.config:
                        new_url = self.config[url]
                        replace = True
                    else:
                        raise ValueError(f"URL '{url}' not found in config. Should sync images first.")
                    line = line.replace(url, new_url)
            new_content += line

        with open(file_name, 'w', encoding='utf-8') as file:
            file.write(new_content)
        if replace:
            print(f"Updated: {file_name}")

    def replace_all_md_images(self):
        md_files = self.get_all_md_files()
        for file in md_files:
            self.replace_img_urls_in_md(file)

class SMMSClient:
    def __init__(self, endpoint, username, password):
        self.username = username
        self.password = password
        self.endpoint = endpoint.strip('/')
        data = {
            'username': self.username,
            'password': self.password,
        }
        url = f"{self.endpoint}/token"
        resp = requests.post(url, data=data).json()
        self.token = resp['data']['token']
        self.headers = {
            'Authorization': self.token,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        }

    def upload(self, image_path):
        url = f"{self.endpoint}/upload"
        with open(image_path, 'rb') as f:
            image = {'smfile': f}
            try:
                resp = requests.post(url, files=image, headers=self.headers).json()
                if resp['success']:
                    return resp['data']['url']
                elif resp['code'] == 'image_repeated':
                    return resp['images']
                else:
                    raise Exception(f"Upload failed: {resp['message']}")
            except Exception as e:
                print(e)
                raise Exception(f"Error uploading image: {e}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Sync images and replace markdown image links.")
    parser.add_argument('--dir', help='Markdown directory', required=True)
    parser.add_argument('--pic', help='Images directory', required=True)
    parser.add_argument('--config', help='Config file path', default='config.json')
    parser.add_argument('--endpoint', help='SM.MS API endpoint', default='https://sm.ms/api/v2/')
    parser.add_argument('--username', help='SM.MS username', default=os.getenv('SMMS_USERNAME'))
    parser.add_argument('--password', help='SM.MS password', default=os.getenv('SMMS_PASSWORD'))
    args = parser.parse_args()

    sync = ImageMarkdownSync(
        img_dir=args.pic,
        md_dir=args.dir,
        upload_client=SMMSClient(args.endpoint, args.username, args.password),
        config_path=args.config
    )

    sync.sync_images()
    sync.replace_all_md_images()
