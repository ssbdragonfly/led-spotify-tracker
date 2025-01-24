import board
import displayio
import framebufferio
import terminalio
from adafruit_display_text import label
import rgbmatrix
import requests
import time
import base64
from io import BytesIO
from PIL import Image

CLIENT_ID = 'your client id here'
CLIENT_SECRET = 'your client secret here'
REFRESH_TOKEN = 'your refresh token here'

def refresh_access_token():
    token_url = 'https://accounts.spotify.com/api/token'
    auth = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()

    headers = {
        'Authorization': f'Basic {auth}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': REFRESH_TOKEN
    }

    response = requests.post(token_url,headers=headers,data=data)
    if response.status_code== 200:
        return response.json()['access_token']
    else:
        print(f"error refreshing token: {response.status_code}, {response.text}")
        return None

def get_spotify_currently_playing(access_token):
    SPOTIFY_API_URL = "https://api.spotify.com/v1/me/player/currently-playing"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(SPOTIFY_API_URL,headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data and data.get('is_playing'):
                track_name = data['item']['name']
                artists_name = ""
                for artist in data['item']['artists']:
                    artists_name += artist['name'] + ", "
                artists_name = artists_name[:-2]
                album_art_url = data['item']['album']['images'][0]['url']
                return track_name, artists_name, album_art_url
        elif response.status_code== 401:
            print("access token expired")
            return None

        return "No Track Playing","No Artist",None
    except Exception as e:
        print(f"spotify api Error: {e}")
        return "Error", "Error",None

def fetch_album_art(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
        else:
            print(f"Failed to fetch album art: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching album art: {e}")
        return None

def image_to_bitmap(image):
    image = image.convert('RGB').resize((32, 32))
    pixel_data = image.getdata()
    bitmap = displayio.Bitmap(32, 32,len(pixel_data))
    palette = displayio.Palette(len(pixel_data))
    for i, color in enumerate(pixel_data):
        bitmap[i% 32,i // 32] = i
        palette[i] = (color[0],color[1],color[2])
    return bitmap, palette

def main():
    access_token = refresh_access_token()
    if not access_token:
        print("couldnt get initial access token. exiting process")
        return

    matrix = rgbmatrix.RGBMatrix(
        width=64, height=32, bit_depth=3,
        rgb_pins=[board.D6, board.D5, board.D9, board.D11, board.D10, board.D12],
        addr_pins=[board.A5, board.A4, board.A3, board.A2],
        clock_pin=board.D13, latch_pin=board.D0, output_enable_pin=board.D1
    )

    display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)
    main_screen = displayio.Group()
    background = displayio.TileGrid(
        displayio.Bitmap(display.width,display.height,1),
        pixel_shader=displayio.Palette(1)
    )
    background.pixel_shader[0] = 0x000000
    main_screen.append(background)
    waveform_step = 0
    text_scroll_step = 0

    while True:
        result = get_spotify_currently_playing(access_token)
        if result is None:
            access_token = refresh_access_token()
            if not access_token:
                print("couldnt refresh the access token, will retry in a min")
                time.sleep(60)
                continue
            result = get_spotify_currently_playing(access_token)

        track,artist,album_art_url = result

        while len(main_screen) > 1:
            main_screen.pop()
        if album_art_url:
            album_art_image = fetch_album_art(album_art_url)
            if album_art_image:
                try:
                    album_bitmap,album_palette = image_to_bitmap(album_art_image)
                    album_art = displayio.TileGrid(album_bitmap, pixel_shader=album_palette,x=0,y=0)
                    main_screen.append(album_art)
                except Exception as e:
                    print(f"error displaying album art: {e}")

        track_scroll_text = track + "   " 
        artist_scroll_text = artist + "   "
        visible_track = track_scroll_text[text_scroll_step:text_scroll_step + 15]
        visible_artist = artist_scroll_text[text_scroll_step:text_scroll_step + 15]
        track_label = label.Label(
            terminalio.FONT,
            text=visible_track,
            color=0xFFFFFF,
            scale=1,
            x=34,
            y=5
        )
        artist_label = label.Label(
            terminalio.FONT,
            text=visible_artist,
            color=0xAAAAAA,
            scale=1,
            x=34,
            y=15
        )

        main_screen.append(track_label)
        main_screen.append(artist_label)
        for i in range(33,64,4):
            height = 4 + 2 * ((i//4 + waveform_step)% 4)
            for y in range(28 - height//2,28 + height//2):
                if 0 <=y <32:
                    waveform_pixel = displayio.TileGrid(
                        displayio.Bitmap(1, 1, 1),
                        pixel_shader=displayio.Palette(1),
                        x=i, y=y
                    )
                    waveform_pixel.pixel_shader[0] = 0x00FF00
                    main_screen.append(waveform_pixel)

        display.root_group = main_screen
        display.refresh()
        waveform_step += 1
        text_scroll_step = (text_scroll_step + 1) % len(track_scroll_text)
        time.sleep(0.1)

if __name__ == '__main__':
    main()
