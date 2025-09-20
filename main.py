import requests

def upload_image_to_wechat_temp_media(image_path, access_token):
    """
    上传图片到微信临时素材，返回media_id
    """
    url = f"https://api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=image"
    with open(image_path, 'rb') as img_file:
        files = {'media': img_file}
        response = requests.post(url, files=files)
    result = response.json()
    if 'media_id' in result:
        return result['media_id']
    else:
        print("上传失败:", result)
        return None

def get_wechat_media_url(media_id, access_token):
    """
    获取微信临时素材的URL
    """
    url = f"https://api.weixin.qq.com/cgi-bin/media/get?access_token={access_token}&media_id={media_id}"
    # 直接返回URL即可，微信会返回图片流，可以用作图片外链
    return url

""" 
{
  "access_token": "96_ebPm1amjxNgLzKnxLnsM0EUgynVDWIx3hvarORfPogS4IC7ylwmZObFu1vMOuFKsmRKgZQ0r4bthL1jgyjhARe_FoJx9boI4rMd5q4jwXTwOn6ZOsqnRBOenriEOBVcABAJWQ",
  "message": "Success"
}

 """

access_token = "96_ebPm1amjxNgLzKnxLnsM0EUgynVDWIx3hvarORfPogS4IC7ylwmZObFu1vMOuFKsmRKgZQ0r4bthL1jgyjhARe_FoJx9boI4rMd5q4jwXTwOn6ZOsqnRBOenriEOBVcABAJWQ"

def main():
    media_id = upload_image_to_wechat_temp_media('./images/3.png', access_token)
    url = get_wechat_media_url(media_id, access_token)
    print("url", url)
    # Open a file in read mode
    # file = open('./data/producthunt-daily-2025-09-14.md', 'r', encoding='utf-8')
    # content = file.read()
    # html = markdown.markdown(content)
    # print("html", html)   
    # with open('./producthunt-daily-2025-09-14.html', 'w', encoding='utf-8') as f:
    #     f.write(html)

    

if __name__ == "__main__":
    main()
