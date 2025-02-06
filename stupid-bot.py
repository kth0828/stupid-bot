import discord
from discord.ext import commands
from discord import app_commands
import requests
import yt_dlp as YoutubeDL
import asyncio
import random
import os
import re
import json
import asyncio
from koreanbots import Koreanbots
from datetime import datetime, timedelta, timezone
from gtts import gTTS
from yt_dlp import YoutubeDL
from dico_token import Token
from koreanbots_token import BOT_ID, Koreanbots_Token
from googletrans import Translator, LANGUAGES

tts_status = {}  # {guild_id: True/False}

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # YTDL 및 FFMPEG 설정
        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'auto',
        }
        self.FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }
        self.ytdl = YoutubeDL(self.YTDL_OPTIONS)

        # ✅ Koreanbots API 클라이언트 설정
        self.BOT_ID = BOT_ID
        self.koreanbots_client = Koreanbots(api_key=Koreanbots_Token)

    async def ensure_voice(self, interaction: discord.Interaction):
        """봇이 음성 채널에 연결되었는지 확인하고 필요 시 연결"""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("먼저 음성 채널에 들어가주세요!")
            return None
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        return interaction.guild.voice_client

    @app_commands.command(name="입장", description="봇이 음성 채널에 들어갑니다.")
    async def join(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("먼저 음성 채널에 들어가주세요!")
            return

        channel = interaction.user.voice.channel
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.move_to(channel)
            await interaction.response.send_message(f"음성 채널을 **{channel.name}**로 이동했습니다.")
        else:
            await channel.connect()
            await interaction.response.send_message(f"음성 채널 **{channel.name}**에 연결되었습니다.")

    @app_commands.command(name="퇴장", description="봇이 음성 채널에서 나갑니다.")
    async def leave(self, interaction: discord.Interaction):
    # 봇이 음성 채널에 연결되어 있는지 확인
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("음성 채널에서 퇴장했습니다.")
        else:
            await interaction.response.send_message("⚠️ 봇이 현재 음성 채널에 연결되어 있지 않습니다.")

    @app_commands.command(name="재생", description="YouTube URL을 통해 음악을 재생합니다.")
    async def play(self, interaction: discord.Interaction, url: str):
        user_id = interaction.user.id
        voice_client = await self.ensure_voice(interaction)
        if not voice_client:
            return

        await interaction.response.send_message(f"🔄 YouTube에서 음악을 검색 중입니다: {url}", ephemeral=True)

        # ✅ Koreanbots API를 사용하여 하트 투표 여부 확인 (하트 보상 코드 참고)
        try:
            response = await self.koreanbots_client.get_bot_vote(user_id, self.BOT_ID)
            voted = response.data.voted  # True = 하트 누름, False = 하트 안 누름
        except Exception as e:
            await interaction.followup.send(f"⚠️ API 오류 발생: ```{e}```", ephemeral=True)
            return

        try:
            # URL 정보를 비동기적으로 처리
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: self.ytdl.extract_info(url, download=False))
            if not data:
                await interaction.followup.send("유효하지 않은 URL입니다. 다시 시도해주세요.")
                return

            song_url = data["url"]
            title = data.get("title", "Unknown Title")
            source = discord.FFmpegPCMAudio(song_url, **self.FFMPEG_OPTIONS)

            if voice_client.is_playing():
                voice_client.stop()
            voice_client.play(source, after=lambda e: print(f"오류 발생: {e}") if e else None)

            await interaction.followup.send(f"🎶 **{title}** 음악이 재생됩니다!")

            # ✅ 하트를 누르지 않은 유저에게 하트 유도 임베드 노출 (음악 재생 후)
            if not voted:
                embed = discord.Embed(
                    title="💖 하트를 눌러주세요!",
                    description=(
                        "봇을 계속 사용하려면 [여기에서 하트를 눌러주세요](https://koreanbots.dev/bots/1321071792772612127)!\n\n"
                        "✅ 하트를 누르면 전체 기능을 제한 없이 사용할 수 있습니다!"
                    ),
                    color=0xFF0000
                )
                embed.set_footer(text="하트를 눌러주시면 큰 힘이 됩니다! 😊")
                await interaction.followup.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"⚠️ 음악 재생 중 오류가 발생했습니다: {e}")

    @app_commands.command(name="볼륨", description="플레이어의 볼륨을 조절합니다.")
    async def volume(self, interaction: discord.Interaction, volume: int):
        if volume < 0 or volume > 100:
            await interaction.response.send_message("볼륨은 0에서 100 사이의 값이어야 합니다.")
            return

        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.source:
            await interaction.response.send_message("현재 재생 중인 음악이 없습니다.")
            return

        voice_client.source.volume = volume / 100
        await interaction.response.send_message(f"🔊 볼륨이 {volume}%로 설정되었습니다.")

    @app_commands.command(name="중지", description="음악을 정지하고 음성 채널에서 나갑니다.")
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.response.send_message("현재 음성 채널에 연결되어 있지 않습니다.")
            return

        await voice_client.disconnect()
        await interaction.response.send_message("🛑 음악이 정지되었고 음성 채널에서 나갔습니다.")

    @app_commands.command(name="일시정지", description="현재 재생 중인 음악을 일시정지합니다.")
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_playing():
            await interaction.response.send_message("현재 재생 중인 음악이 없습니다.")
            return

        voice_client.pause()
        await interaction.response.send_message("⏸️ 음악이 일시 정지되었습니다.")

    @app_commands.command(name="재개", description="일시정지된 음악을 다시 재생합니다.")
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if not voice_client or not voice_client.is_paused():
            await interaction.response.send_message("재개할 음악이 없습니다.")
            return

        voice_client.resume()
        await interaction.response.send_message("▶️ 음악이 다시 재생됩니다.")

async def setup(bot):
    await bot.add_cog(Music(bot))
    await bot.tree.sync()
       
# OpenWeatherMap API 키 설정
API_KEY = "2d5884a12ab4746be800db4b227115f3"
BASE_URL = "http://api.openweathermap.org/data/2.5/group"
allowed_channel_id = None

# Utility Cog
class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="날씨", description="특정 도시의 날씨 정보를 가져옵니다.")
    async def weather(self, interaction: discord.Interaction, city_name: str):
        city_ids = {
            "서울": "1835848",
            "부산": "1838524",
            "인천": "1835327",
            "대구": "1843564",
            "대전": "1835235",
            "광주": "1841811",
            "울산": "1833747",
            "제주": "1846266",
            "수원": "1835553",
            "평택": "1835895",
            "김포": "1841810",
            "평양": "1871859"
        }
        city_id = city_ids.get(city_name)
        if not city_id:
            await interaction.response.send_message("지원하지 않는 도시입니다. 추가를 원할 경우 개발자에게 문의하세요.", ephemeral=True)
            return

        params = {
            "id": city_id,
            "appid": API_KEY,
            "units": "metric",
            "lang": "kr"
        }
        try:
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()['list'][0]

            if city_name == "평양":
                await interaction.response.send_message("😲 당신은 간첩인가요? ...일단 알려드리겠습니다! 🕵️", ephemeral=True)

            # 임베드 생성
            embed = discord.Embed(
                title=f"{city_name}의 날씨 정보",
                color=discord.Color.blue(),
                description="실시간 날씨 정보를 확인하세요!"
            )
            embed.add_field(name="🌡️ 온도", value=f"{data['main']['temp']}°C", inline=False)
            embed.add_field(name="💧 습도", value=f"{data['main']['humidity']}%", inline=False)
            embed.add_field(name="☁️ 날씨", value=f"{data['weather'][0]['description']}", inline=False)
            embed.add_field(name="💨 바람", value=f"{data['wind']['speed']} m/s", inline=False)
            embed.set_footer(text="Powered by OpenWeatherMap", icon_url="https://openweathermap.org/themes/openweathermap/assets/img/logo_white_cropped.png")

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message("날씨 정보를 가져오는 데 실패했습니다.", ephemeral=True)

    @app_commands.command(name="청소", description="특정 수의 메시지를 삭제합니다.")
    async def clear(self, interaction: discord.Interaction, amount: int):
        if amount < 1:
          await interaction.response.send_message("삭제할 메시지 수는 1 이상이어야 합니다.", ephemeral=True)
          return

     # 초기 응답 (비공개)
        await interaction.response.defer(ephemeral=True)

        try:
        # 메시지 삭제 작업
         deleted = await interaction.channel.purge(limit=amount)
        # 작업 완료 후 사용자에게 알림
         await interaction.followup.send(f"🧹 {len(deleted)}개의 메시지가 삭제되었습니다.")
        except discord.Forbidden:
            await interaction.followup.send("❌ 메시지를 삭제할 권한이 없습니다.")
        except discord.HTTPException:
           await interaction.followup.send("❌ 메시지를 삭제하는 중 오류가 발생했습니다.")

    @app_commands.command(name="번역", description="텍스트를 원하는 언어로 번역합니다.")
    async def translate(self, interaction: discord.Interaction, text: str, dest_lang: str):
        translator = Translator()
        try:
            result = translator.translate(text, dest=dest_lang)
            await interaction.response.send_message(f"🌐 번역 결과:\n'{text}' → '{result.text}'")
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 번역 중 오류가 발생했습니다: {e}")

    @app_commands.command(name="번역언어", description="번역 지원 언어 목록을 보여줍니다.")
    async def supported_languages(self, interaction: discord.Interaction):
        languages = ', '.join([f"{code}: {name}" for code, name in LANGUAGES.items()])
        await interaction.response.send_message(f"🌍 지원되는 언어 목록:\n{languages}")

    @app_commands.command(name="봇상태", description="현재 봇의 상태를 표시합니다.")
    async def status(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)  # 봇의 핑 (ms)
        server_count = len(self.bot.guilds)  # 봇이 속한 서버 수
        user_count = sum(guild.member_count for guild in self.bot.guilds)  # 모든 서버의 멤버 수 합계

        embed = discord.Embed(title="🤖 봇 상태", color=0x00ff00)
        embed.add_field(name="핑", value=f"{latency}ms", inline=True)
        embed.add_field(name="서버 수", value=f"{server_count}개", inline=True)
        embed.add_field(name="사용자 수", value=f"{user_count}명", inline=True)
        embed.set_footer(text=f"요청한 유저: {interaction.user}", icon_url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="정보", description="봇의 정보를 보여줍니다.")
    async def show_bot_info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🤖 봇 정보",
            description="디스코드 서버를 더욱 편리하게 관리하고 재미있는 기능을 제공하는 멀티기능 봇입니다.",
            color=0x3498db
        )
        embed.add_field(name="📅 생성 날짜", value="2024년 12월 23일", inline=False)
        embed.add_field(name="📋 주요 기능", value="음악 재생, 번역, 게임, TTS와 같은 유틸리티 명령어 제공", inline=False)
        embed.add_field(name="👨‍💻 개발자", value="_kth. or kth#6249", inline=False)
        embed.add_field(name="💻 GitHub", value="[프로젝트 링크](https://github.com/kth0828/stupid-bot.git)", inline=False)
        embed.set_thumbnail(url="https://i.ibb.co/80yWcDg/image.jpg")  # 봇의 로고 URL
        embed.set_footer(text="이 봇은 맞으면서 컸습니다.")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Utility(bot))
    await bot.tree.sync()
      
# Game Cog
class Game(commands.Cog, name="게임"):
    def __init__(self, bot):
        self.bot = bot

intents = discord.Intents.default()
intents.message_content = True  # 메시지 콘텐츠 읽기 활성화

bot = commands.Bot(command_prefix="!", intents=intents)  # 수정된 intents 전달


tts_channel_id = None  # TTS 활성화된 채널 ID 저장
tts_channel_ids = set()

# JSON 파일 경로
JSON_FOLDER = "json_data"
TTS_SETTINGS_FILE = f"{JSON_FOLDER}/tts_settings.json"

# TTS 채널 정보 저장 함수
def save_tts_settings(tts_channel_ids):
    """
    TTS 설정을 JSON 파일에 저장.
    :param tts_channel_ids: {guild_id: tts_channel_id} 형태의 딕셔너리
    """
    os.makedirs(JSON_FOLDER, exist_ok=True)  # 폴더가 없으면 생성
    with open(TTS_SETTINGS_FILE, "w") as f:
        json.dump(tts_channel_ids, f)

# TTS 채널 정보 불러오기 함수
def load_tts_settings():
    """
    JSON 파일에서 TTS 설정을 불러옴.
    :return: {guild_id: tts_channel_id} 형태의 딕셔너리
    """
    if not os.path.exists(TTS_SETTINGS_FILE):
        return {}  # 파일이 없으면 빈 딕셔너리 반환
    with open(TTS_SETTINGS_FILE, "r") as f:
        return json.load(f)

# 텍스트 클리닝 함수
def clean_text(text):
    return text.strip()

# 음성 채널 연결 함수
async def connect_to_voice_channel(channel):
    if not channel:
        return None
    try:
        return await channel.connect()
    except discord.ClientException:
        return channel.guild.voice_client

# 예시: 서버별 TTS 설정 관리
tts_channel_ids = load_tts_settings()  # 기존 설정 불러오기

# 특정 서버의 TTS 채널 ID 설정
def set_tts_channel(guild_id, channel_id):
    """
    특정 서버의 TTS 채널 ID를 설정.
    :param guild_id: 서버 ID
    :param channel_id: TTS 채널 ID
    """
    tts_channel_ids[guild_id] = channel_id
    save_tts_settings(tts_channel_ids)

# 특정 서버의 TTS 채널 ID 가져오기
def get_tts_channel(guild_id):
    """
    특정 서버의 TTS 채널 ID를 반환.
    :param guild_id: 서버 ID
    :return: TTS 채널 ID 또는 None
    """
    return tts_channel_ids.get(guild_id)

# TTS 채널 설정 명령어
@bot.tree.command(name="tts설정", description="TTS를 활성화할 채널을 설정합니다.")
async def set_tts_channel(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)  # 서버 ID
    channel_id = interaction.channel.id  # 채널 ID

    # 서버별 TTS 채널 설정
    tts_channel_ids[guild_id] = channel_id
    save_tts_settings(tts_channel_ids)  # JSON 파일에 저장

    await interaction.response.send_message(
        f"✅ TTS가 이 채널(<#{channel_id}>)에서 활성화되었습니다!"
    )

# TTS 채널 비활성화 명령어
@bot.tree.command(name="tts해제", description="TTS를 비활성화합니다.")
async def disable_tts(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)  # 서버 ID

    # TTS 채널 비활성화
    if guild_id in tts_channel_ids:
        del tts_channel_ids[guild_id]
        save_tts_settings(tts_channel_ids)  # JSON 파일에 저장
        await interaction.response.send_message("❌ TTS가 비활성화되었습니다!")
    else:
        await interaction.response.send_message("⚠️ 현재 활성화된 TTS 설정이 없습니다.")

def clean_text(text):
    """특수 문자 및 빈 문자열 처리"""
    text = re.sub(r'[^\w\s가-힣]', '', text)  # 한국어, 영어, 숫자만 허용
    return text.strip()

# on_message 이벤트
@bot.event
async def on_message(message):
    # 봇의 메시지는 무시
    if message.author.bot:
        return

    guild_id = str(message.guild.id)

    # TTS가 활성화된 채널인지 확인
    if guild_id not in tts_channel_ids or message.channel.id != tts_channel_ids[guild_id]:
        return

    # 음성 채널 연결 확인
    if not message.guild.voice_client:
        # 봇이 연결되지 않은 경우, 호출자의 음성 채널로 연결
        if message.author.voice and message.author.voice.channel:
            await connect_to_voice_channel(message.author.voice.channel)
        else:
            await message.channel.send("⚠️ TTS를 실행하려면 음성 채널에 먼저 연결되어야 합니다.")
            return

    try:
        # 메시지 내용 처리
        text = clean_text(message.content)
        if not text:
            await message.channel.send("⚠️ 처리할 수 있는 텍스트가 없습니다.")
            return

        # TTS 음성 생성 및 재생
        tts = gTTS(text=text, lang="ko")
        tts.save("message.mp3")

        message.guild.voice_client.play(
            discord.FFmpegPCMAudio("message.mp3"),
            after=lambda e: os.remove("message.mp3") if os.path.exists("message.mp3") else None
        )
    except Exception as e:
        print(f"오류 발생: {e}")

    # 명령어 처리
    await bot.process_commands(message)

@bot.event
async def on_ready():
    load_tts_settings()
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    custom_activity = discord.CustomActivity(
        name="📺 중증외상센터 보는 중",  # 표시될 상태 메시지
        type=discord.ActivityType.playing  # Playing 대신 Watching, Listening 등도 가능
    )
    print(f"Cogs: {list(bot.cogs.keys())}")  # 로드된 Cog 확인
    try:
        synced = await bot.tree.sync()  # 애플리케이션 명령어 동기화
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료!")
    except Exception as e:
        print(f"동기화 중 오류 발생: {e}")
    await bot.change_presence(activity=custom_activity)

# 슬래시 명령어 정의
@bot.tree.command(name="핑", description="봇의 응답 속도를 확인합니다.")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)  # 밀리초 단위
    await interaction.response.send_message(f"🏓 퐁! 현재 응답 속도는 {latency}ms 입니다.")

# JSON 파일 경로
JSON_FOLDER = "json_data"
POINTS_FILE = f"{JSON_FOLDER}/points.json"
ATTENDANCE_FILE = f"{JSON_FOLDER}/attendance.json"

# points.json 파일이 없으면 빈 딕셔너리로 초기화
# JSON 데이터 읽기
def load_points():
    try:
        with open(POINTS_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}  # 파일이 없으면 빈 딕셔너리 반환

# JSON 데이터 저장
def save_points(data):
    with open(POINTS_FILE, "w") as file:
        json.dump(data, file, indent=4)

# 출석 체크용 JSON 파일 경로
# JSON 데이터 로드
def load_data(file):
    try:
        with open(file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # 파일이 없으면 빈 딕셔너리 반환

# JSON 데이터 저장
def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

# 포인트 추가
def add_points(user_id, amount):
    data = load_points()
    data[user_id] = data.get(user_id, 0) + amount
    save_points(data)

# 포인트 감소
def deduct_points(user_id, amount):
    data = load_points()
    if user_id in data and data[user_id] >= amount:
        data[user_id] -= amount
        save_points(data)
        return True  # 성공적으로 차감
    return False  # 포인트 부족

# 출석 확인
def has_checked_in_today(user_id):
    data = load_data(ATTENDANCE_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    return data.get(user_id) == today

# 출석 기록 업데이트
def mark_checked_in(user_id):
    data = load_data(ATTENDANCE_FILE)
    today = datetime.now().strftime("%Y-%m-%d")
    data[user_id] = today
    save_data(ATTENDANCE_FILE, data)

# 포인트 조회
def get_points(user_id):
    data = load_points()
    return data.get(user_id, 0)

@bot.tree.command(name="포인트", description="현재 포인트를 확인합니다.")
async def points(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    points = get_points(user_id)
    formatted_points = f"{points:,}"  # 쉼표 추가
    await interaction.response.send_message(f"{interaction.user.name}님의 포인트는 {formatted_points}점입니다.")

@bot.tree.command(name="포인트양도", description="다른 사용자에게 포인트를 양도합니다.")
@app_commands.describe(target="포인트를 받을 사용자", amount="양도할 포인트 금액")
async def transfer_points(interaction: discord.Interaction, target: discord.User, amount: int):
    # 호출한 사용자와 대상 사용자 ID
    sender_id = str(interaction.user.id)
    target_id = str(target.id)
    
    # 포인트 데이터 로드
    sender_points = get_points(sender_id)
    
    # 양도 금액 검증
    if sender_points < amount:
        await interaction.response.send_message(
            f"🚫 {interaction.user.name}님, 포인트가 부족합니다! 현재 포인트: {sender_points:,}점.",
            ephemeral=True  # 개인 메시지로 전송
        )
        return
    
    if amount <= 0:
        await interaction.response.send_message(
            "🚫 유효하지 않은 금액입니다. 양도할 포인트는 1점 이상이어야 합니다.",
            ephemeral=True
        )
        return

    # 포인트 양도 처리
    deduct_points(sender_id, amount)  # 양도자 포인트 차감
    add_points(target_id, amount)    # 대상 사용자 포인트 추가

    # 결과 메시지
    await interaction.response.send_message(
        f"✅ {interaction.user.name}님이 {target.name}님에게 {amount:,} 포인트를 양도했습니다!"
    )

@bot.tree.command(name="도박", description="포인트를 베팅합니다.")
@app_commands.describe(amount="베팅할 금액")
async def bet(interaction: discord.Interaction, amount: int):
    user_id = str(interaction.user.id)
    current_points = int(get_points(user_id))  # 포인트를 정수로 변환

    if current_points < amount:
        # 포인트가 부족한 경우
        formatted_points = f"{current_points:,}"  # 쉼표 추가
        await interaction.response.send_message(
            f"{interaction.user.name}님, 포인트가 부족합니다. 현재 포인트: {formatted_points}점."
        )
        return

    # 성공/실패 결과 결정 (50% 확률)
    result = random.choice(["win", "lose"])

    if result == "win":
        # 성공: 베팅액의 1.5배 지급
        winnings = int(amount * 1.5)  # float 계산 후 정수 변환
        add_points(user_id, winnings)
        formatted_winnings = f"{winnings:,}"  # 쉼표 추가
        formatted_current_points = f"{int(get_points(user_id)):,}"  # 쉼표 추가
        await interaction.response.send_message(
            f"🎉 {interaction.user.name}님이 베팅에 성공했습니다! "
            f"{formatted_winnings} 포인트를 획득했습니다! 현재 포인트: {formatted_current_points}점."
        )
    else:
        # 실패: 베팅액 소멸
        deduct_points(user_id, amount)
        formatted_amount = f"{amount:,}"  # 쉼표 추가
        formatted_current_points = f"{int(get_points(user_id)):,}"  # 쉼표 추가
        await interaction.response.send_message(
            f"💔 {interaction.user.name}님이 베팅에 실패했습니다. {formatted_amount} 포인트를 잃었습니다. "
            f"현재 포인트: {formatted_current_points}점."
        )

@bot.tree.command(name="주사위도박", description="포인트를 베팅합니다.")
@app_commands.describe(amount="베팅할 금액", choice="베팅할 옵션 (짝수/홀수)")
async def bet(interaction: discord.Interaction, amount: int, choice: str):
    user_id = str(interaction.user.id)
    current_points = int(get_points(user_id))  # 포인트를 정수로 변환

    if current_points < amount:
        formatted_points = f"{current_points:,}"  # 쉼표 추가
        await interaction.response.send_message(
            f"{interaction.user.name}님, 포인트가 부족합니다. 현재 포인트: {formatted_points}점."
        )
        return

    if choice not in ["짝수", "홀수"]:
        await interaction.response.send_message("유효한 옵션을 선택해주세요: `짝수` 또는 `홀수`.")
        return

    # 주사위 굴리기 (1~6)
    roll = random.randint(1, 6)
    result = "짝수" if roll % 2 == 0 else "홀수"

    if result == choice:
        winnings = int(amount * 1.5)  # float 결과를 정수로 변환
        add_points(user_id, winnings)
        formatted_winnings = f"{winnings:,}"  # 쉼표 추가
        formatted_points = f"{int(get_points(user_id)):,}"  # 쉼표 추가
        await interaction.response.send_message(
            f"🎲 주사위 값: {roll} ({result}). {interaction.user.name}님이 베팅에 성공했습니다! "
            f"{formatted_winnings} 포인트를 획득했습니다. 현재 포인트: {formatted_points}점."
        )
    else:
        deduct_points(user_id, amount)
        formatted_amount = f"{amount:,}"  # 쉼표 추가
        formatted_points = f"{int(get_points(user_id)):,}"  # 쉼표 추가
        await interaction.response.send_message(
            f"🎲 주사위 값: {roll} ({result}). {interaction.user.name}님이 베팅에 실패했습니다. "
            f"{formatted_amount} 포인트를 잃었습니다. 현재 포인트: {formatted_points}점."
        )

@bot.tree.command(name="룰렛", description="룰렛 게임에 베팅합니다.")
@app_commands.describe(amount="베팅할 금액", number="룰렛 숫자 (1-10 중 선택)")
async def roulette(interaction: discord.Interaction, amount: int, number: int):
    user_id = str(interaction.user.id)
    current_points = int(get_points(user_id))

    # 포인트 부족 확인
    if current_points < amount:
        formatted_points = f"{current_points:,}"  # 쉼표 추가
        embed = discord.Embed(
            title="포인트 부족!",
            description=f"현재 포인트: **{formatted_points}점**",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 숫자 범위 확인
    if number < 1 or number > 10:
        embed = discord.Embed(
            title="숫자 입력 오류",
            description="룰렛 숫자는 **1에서 10** 사이여야 합니다.",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed)
        return

    # 초기 메시지 전송 (룰렛 이미지 포함)
    embed = discord.Embed(
        title="🎡 룰렛이 돌아갑니다!",
        description="룰렛이 회전 중입니다... 잠시만 기다려 주세요!",
        color=discord.Color.blue()
    )
    embed.set_image(url="https://i.ibb.co/GHS2p9Y/online-video-cutter-com.gif")  # 돌아가는 룰렛 이미지 추가
    await interaction.response.send_message(embed=embed)

    # 메시지 업데이트를 위해 원본 메시지 가져오기
    message = await interaction.original_response()

    # 룰렛 애니메이션 시간 대기
    await asyncio.sleep(6)  # 3초 대기 (룰렛이 도는 동안)

    # 최종 결과 계산
    spin_result = random.randint(1, 10)

    # 결과 확인
    if spin_result == number:
        winnings = int(amount * 10)
        add_points(user_id, winnings)
        formatted_winnings = f"{winnings:,}"
        formatted_points = f"{int(get_points(user_id)):,}"
        result_color = discord.Color.green()
        result_message = (
            f"🎉 축하합니다! {interaction.user.name}님이 베팅에 성공했습니다!\n"
            f"룰렛 숫자: **{spin_result}**\n"
            f"획득 포인트: **{formatted_winnings}점**\n"
            f"현재 포인트: **{formatted_points}점**"
        )
    else:
        deduct_points(user_id, amount)
        formatted_amount = f"{amount:,}"
        formatted_points = f"{int(get_points(user_id)):,}"
        result_color = discord.Color.red()
        result_message = (
            f"😢 아쉽습니다! {interaction.user.name}님이 베팅에 실패했습니다.\n"
            f"룰렛 숫자: **{spin_result}**\n"
            f"잃은 포인트: **{formatted_amount}점**\n"
            f"현재 포인트: **{formatted_points}점**"
        )

    # 최종 결과 Embed 전송
    result_embed = discord.Embed(
        title="🎡 룰렛 결과",
        description=result_message,
        color=result_color
    )
    await message.edit(embed=result_embed)  # 메시지 업데이트

# 경마 게임 슬래시 명령어
@bot.tree.command(name="경마", description="포인트를 배팅하고 경마 게임을 합니다!")
@app_commands.describe(bet="베팅할 금액", horse_number="베팅할 말(1-4)")
async def horse_race(interaction: discord.Interaction, bet: int, horse_number: int):
    # 입력값 검증
    if horse_number not in [1, 2, 3, 4]:
        await interaction.response.send_message("말 번호는 1에서 4 사이의 숫자여야 합니다!", ephemeral=True)
        return
    if bet <= 0:
        await interaction.response.send_message("배팅 금액은 1 이상이어야 합니다!", ephemeral=True)
        return

    # 포인트 데이터 로드
    points = load_points()
    user_id = str(interaction.user.id)

    # 사용자 초기 포인트 설정
    if user_id not in points:
        points[user_id] = 10000

    # 포인트 확인
    if points[user_id] < bet:
        await interaction.response.send_message(
            f"포인트가 부족합니다! 현재 포인트: {int(points[user_id]):,}", ephemeral=True
        )
        return

    # 경주 설정
    horses = ["🏇 1번 말", "🏇 2번 말", "🏇 3번 말", "🏇 4번 말"]
    progress = [0] * 4
    race_length = 20
    winner = None

    # 경주 트랙 생성 함수
    def create_track():
        track = ""
        for i, horse in enumerate(horses):
            position = progress[i]
            track += f"{horse}: " + "⬜" * position + "➡️" + "⬜" * (race_length - position) + "[🏁]\n"
        return track

    # 초기 Embed 생성 (색상 변경)
    embed = discord.Embed(title="🏁 경마 게임 시작!", color=discord.Color.orange())
    embed.description = create_track()
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()

    # 경주 진행
    while not winner:
        await asyncio.sleep(1)
        for i in range(len(progress)):
            progress[i] += random.randint(1, 3)
            if progress[i] >= race_length:
                progress[i] = race_length
                winner = i + 1
                break

        # Embed 업데이트
        embed.description = create_track()
        embed.set_footer(text="경주가 진행 중입니다...")
        await message.edit(embed=embed)

    # 결과 처리
    if winner == horse_number:
        winnings = bet * 5
        points[user_id] += winnings
        result_message = f"🎉 {horses[winner-1]}이 우승했습니다! 배팅 성공! {int(winnings):,} 포인트를 획득했습니다!"
    else:
        points[user_id] -= bet
        result_message = f"😢 {horses[winner-1]}이 우승했습니다. 배팅 실패! {int(bet):,} 포인트를 잃었습니다."

    # 포인트 저장
    save_points(points)

    # 최종 결과 Embed (승리/패배 색상 변경)
    result_color = discord.Color.gold() if winner == horse_number else discord.Color.red()
    embed = discord.Embed(title="🏆 경마 게임 결과!", description=create_track(), color=result_color)
    embed.add_field(name="🏆 우승마", value=f"{horses[winner-1]}이 우승했습니다!", inline=False)
    embed.add_field(name="결과", value=result_message, inline=False)
    embed.set_footer(text=f"현재 {interaction.user.name}님의 포인트: {int(points[user_id]):,}")
    await message.edit(embed=embed)

DEVELOPER_ID = 883660105298608149  # 개발자의 디스코드 ID를 여기에 입력

@bot.tree.command(name="추가", description="포인트를 추가합니다. (개발자 전용)")
@app_commands.describe(user="포인트를 추가할 사용자", amount="추가할 금액")
async def add_points_cmd(interaction: discord.Interaction, user: discord.User, amount: int):
    # 호출한 사용자의 ID 확인
    if interaction.user.id == DEVELOPER_ID:
        user_id = str(user.id)
        add_points(user_id, amount)
        await interaction.response.send_message(f"✅ {user.name}님에게 {amount} 포인트를 추가했습니다!")
    else:
        await interaction.response.send_message(
            "🚫 이 명령어는 개발자만 사용할 수 있습니다.",
            ephemeral=True  # 이 메시지는 호출한 사용자만 볼 수 있음
        )


@bot.tree.command(name="출석체크", description="하루에 한 번 출석 체크로 포인트를 획득합니다.")
async def daily_check_in(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    
    if has_checked_in_today(user_id):
        await interaction.response.send_message(
            f"{interaction.user.name}님, 오늘 이미 출석 체크를 완료하셨습니다! 내일 다시 시도하세요."
        )
    else:
        # 출석 처리 및 포인트 지급
        mark_checked_in(user_id)
        add_points(user_id, 100000)
        current_points = get_points(user_id)
        formatted_points = f"{current_points:,}"  # 3자리마다 , 추가
        await interaction.response.send_message(
            f"✅ {interaction.user.name}님, 출석 체크 완료! 100,000 포인트를 받으셨습니다. "
            f"현재 포인트: {formatted_points}점."
        )

# Koreanbots API 클라이언트 설정
koreanbots_client = Koreanbots(api_key=Koreanbots_Token)

# 유저별 하트 지급 기록 저장
last_vote_time = {}

@bot.tree.command(name="하트보상", description="한국 디스코드 리스트에서 하트를 눌러 포인트를 받습니다.")
async def heart_reward(interaction: discord.Interaction):
    user_id = interaction.user.id

    # Koreanbots API를 사용하여 하트 투표 여부 확인
    try:
        response = await koreanbots_client.get_bot_vote(user_id, BOT_ID)
        if not response.data.voted:
            embed = discord.Embed(
                title="❌ 하트를 누르지 않았어요!",
                description="먼저 한국 디스코드 리스트에서 하트를 눌러주세요!",
                url="https://koreanbots.dev/bots/1321071792772612127",  # ✅ 클릭하면 Koreanbots로 이동
                color=0xFF0000
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    except Exception as e:
        embed = discord.Embed(
            title="⚠️ API 오류 발생!",
            description=f"하트 정보를 가져오는 중 오류가 발생했습니다.\n```{e}```",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # 🔹 최근 보상 지급 시간 확인 (12시간 쿨타임 적용)
    current_time = datetime.now(timezone.utc)  # ✅ 수정된 부분
    if user_id in last_vote_time and current_time - last_vote_time[user_id] < timedelta(hours=12):
        embed = discord.Embed(
            title="⏳ 이미 보상을 받았어요!",
            description="하트 보상은 **12시간마다** 받을 수 있습니다.",
            color=0xFFAA00
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # ✅ 포인트 지급 (100만 포인트)
    points_data = load_points()  # 기존 포인트 데이터 불러오기
    points_data[user_id] = points_data.get(user_id, 0) + 1_000_000
    save_points(points_data)  # 업데이트된 포인트 저장

    # 최근 보상 시간 기록
    last_vote_time[user_id] = current_time  # ✅ 수정된 부분

    # 성공 메시지
    embed = discord.Embed(
        title="🎉 하트 보상 지급 완료!",
        description="💖 한국 디스코드 리스트에서 하트를 눌러주셔서 감사합니다!\n\n💰 **1,000,000 포인트**가 지급되었습니다.",
        color=0x00FF00
    )
    embed.set_footer(text="12시간 후 다시 보상을 받을 수 있습니다!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="랭킹", description="티어와 포인트를 종합하여 랭킹을 확인합니다.")
async def show_ranking(interaction: discord.Interaction, top_n: int = 10):
    """티어와 포인트를 종합하여 랭킹을 출력합니다."""
    
    points = load_points()
    user_data = load_user_data()

    if not points:
        await interaction.response.send_message("포인트 데이터가 없습니다.", ephemeral=True)
        return

    # 티어별 정렬 우선순위 (높을수록 상위 랭크)
    tier_priority = {
        "그랜드마스터": 7,
        "마스터": 6,
        "다이아몬드": 5,
        "플래티넘": 4,
        "골드": 3,
        "실버": 2,
        "브론즈": 1,
        "언랭크": 0
    }

    # 숫자를 라틴 숫자로 변환하는 딕셔너리
    roman_numerals = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V"}

    ranking_list = []
    
    for user_id, point in points.items():
        # 유저 티어 가져오기
        if user_id in user_data and "tier" in user_data[user_id]:
            tier_info = user_data[user_id]["tier"].split()
            tier_name = tier_info[0]  # 티어명 (ex. "브론즈", "실버", ..., "그랜드마스터")

            # 그랜드마스터는 숫자가 없음 → 예외 처리
            if len(tier_info) == 2:
                tier_number = tier_info[1]  # 티어 숫자 (ex. "3")
                roman_tier = roman_numerals.get(tier_number, tier_number)  # 라틴 숫자로 변환
                
                # 💡 마스터 & 그랜드마스터 굵게 처리
                if tier_name in ["마스터", "그랜드마스터"]:
                    tier_display = f"**[{tier_name} {roman_tier}]**"
                else:
                    tier_display = f"[{tier_name} {roman_tier}]"
                
                tier_rank = tier_priority.get(tier_name, 0)  # 티어 우선순위
                numeric_tier = -int(tier_number)  # 숫자가 작을수록 높은 등급
            else:
                # 💡 마스터 & 그랜드마스터 굵게 처리
                if tier_name in ["마스터", "그랜드마스터"]:
                    tier_display = f"**[{tier_name}]**"
                else:
                    tier_display = f"[{tier_name}]"
                
                tier_rank = tier_priority.get(tier_name, 0)  # 최상위 우선순위
                numeric_tier = 0  # 그랜드마스터는 가장 높은 순위이므로 숫자 없음

        else:
            tier_display = "[언랭크]"
            tier_rank = 0  # 언랭크는 가장 낮은 우선순위
            numeric_tier = 0

        # 정렬을 위한 튜플 (티어 우선순위, 티어 숫자(낮을수록 상위), 포인트 내림차순)
        ranking_list.append((tier_rank, numeric_tier, point, user_id, tier_display))

    # 정렬: 티어 우선순위 -> 같은 티어 내에서 숫자가 낮을수록(예: 브론즈 I이 브론즈 V보다 높음) -> 포인트 내림차순
    ranking_list.sort(reverse=True, key=lambda x: (x[0], x[1], x[2]))

    # 상위 N명 선택
    top_players = ranking_list[:top_n]

    # Embed 객체 생성
    embed = discord.Embed(title="📊 티어 & 포인트 종합 랭킹 📊", color=discord.Color.gold())

    # 1등에 왕관 이모지를 추가
    crown_emoji = ["👑"]

    for rank, (tier_rank, tier_num, points, user_id, tier_display) in enumerate(top_players, start=1):
        # 왕관을 추가 (1등만)
        crown = crown_emoji[0] if rank == 1 else ""

        embed.add_field(
            name=f"**{crown} {rank}위**",
            value=f"{tier_display} <@{user_id}>: {int(points):,} 포인트",
            inline=False
        )

    # 메시지 응답
    await interaction.response.send_message(embed=embed)

# 티어 부여 함수
# 유저 데이터를 저장할 파일 경로
JSON_FOLDER = "json_data"
USER_DATA_FILE = f"{JSON_FOLDER}/user_data.json"
POINTS_FILE = f"{JSON_FOLDER}/points.json"

# 티어별 색상 설정 (Embed 색상)
TIER_COLORS = {
    "브론즈": 0xCD7F32,
    "실버": 0xC0C0C0,
    "골드": 0xFFD700,
    "플래티넘": 0x00FFFF,
    "다이아몬드": 0x1E90FF,
    "마스터": 0x9400D3,
    "그랜드마스터": 0xFF4500,
}

# 티어별 이미지 (추후 추가 가능)
TIER_IMAGES = {
    "브론즈": "https://example.com/bronze.png",
    "실버": "https://example.com/silver.png",
    "골드": "https://example.com/gold.png",
    "플래티넘": "https://example.com/platinum.png",
    "다이아몬드": "https://example.com/diamond.png",
    "마스터": "https://example.com/master.png",
    "그랜드마스터": "https://example.com/grandmaster.png",
}

# 유저 데이터 로드
def load_user_data():
    try:
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# 유저 데이터 저장
def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 포인트 로드
def load_points():
    try:
        with open(POINTS_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# 포인트 저장
def save_points(data):
    with open(POINTS_FILE, "w") as file:
        json.dump(data, file, indent=4)

# 티어 부여 함수
def assign_initial_tier():
    tiers = ["브론즈 5", "브론즈 4", "브론즈 3", "브론즈 2", "브론즈 1"]
    probabilities = [0.2, 0.2, 0.2, 0.2, 0.2]
    return random.choices(tiers, probabilities)[0]

def tier_upgrade(current_tier):
    """ 티어 승급 확률을 기반으로 티어 변경 """
    tier_groups = {
        "브론즈": {"next": "실버", "prob": [0.6, 0.2, 0.2]},
        "실버": {"next": "골드", "prob": [0.55, 0.25, 0.2]},
        "골드": {"next": "플래티넘", "prob": [0.5, 0.2, 0.3]},
        "플래티넘": {"next": "다이아몬드", "prob": [0.45, 0.25, 0.3]},
        "다이아몬드": {"next": "마스터", "prob": [0.4, 0.3, 0.3]},
        "마스터": {"next": "그랜드마스터", "prob": [0.4, 0.3, 0.3]},
        "그랜드마스터": {"next": None, "prob": [0.0, 1.0, 0.0]},  # 최고 티어는 변동 없음
    }

    tier_name = current_tier.split()[0]  # 티어 이름 (ex. "브론즈")
    tier_num = int(current_tier.split()[1]) if tier_name != "그랜드마스터" else None  # 티어 숫자 (ex. 3)

    if tier_name not in tier_groups:
        return current_tier  # 잘못된 티어면 변경 없음

    # 확률 적용하여 승급, 유지, 하락 결정
    result = random.choices(["승급", "유지", "하락"], weights=tier_groups[tier_name]["prob"])[0]

    if result == "승급":
        if tier_num and tier_num > 1:
            return f"{tier_name} {tier_num - 1}"
        else:
            next_tier = tier_groups[tier_name]["next"]
            if next_tier:
                return f"{next_tier} 5" if next_tier != "그랜드마스터" else "그랜드마스터"
            else:
                return current_tier
    elif result == "하락":
        if tier_num and tier_num < 5:
            return f"{tier_name} {tier_num + 1}"
        else:
            return current_tier  # 최하위 티어에서 더 내려갈 수 없음
    else:
        return current_tier  # 유지

@bot.tree.command(name="티어", description="티어 시스템과 티어 종류를 설명합니다.")
async def tier_info(interaction: discord.Interaction):
    """ 티어 시스템과 티어 종류에 대한 설명을 제공하는 명령어 """
    
    # Embed 생성
    embed = discord.Embed(
        title="🏆 티어 시스템 안내",
        description="이 서버의 티어 시스템은 **7개의 단계**로 구성되어 있으며, "
                    "포인트를 사용하여 **확률적으로** 승급할 수 있습니다.\n\n"
                    "💡 `/배치고사`를 통해 기본 티어를 부여받고 `/티어상승`으로 티어를 올려보세요!",
        color=discord.Color.gold()
    )

    # 티어별 승급 포인트
    tier_info = {
        "그랜드마스터": (100_000_000, "최고의 유저만 도달할 수 있는 최상위 티어"),
        "마스터": (50_000_000, "매우 숙련된 유저가 도달할 수 있는 티어"),
        "다이아몬드": (10_000_000, "고수들의 전장! 더욱 전략적인 플레이가 필요"),
        "플래티넘": (1_000_000, "상위권 유저들이 속한 티어"),
        "골드": (500_000, "중상위권 유저들이 속한 티어"),
        "실버": (200_000, "평균적인 실력을 가진 유저들의 티어"),
        "브론즈": (100_000, "초보자 및 입문자들이 시작하는 기본 티어")
    }

    # 티어별 설명 추가
    for name, (points, description) in tier_info.items():
        embed.add_field(
            name=f"**{name}**",
            value=f"📌 {description}\n💰 **필요 포인트:** {points:,}",
            inline=False
        )

    # 추가 정보
    embed.set_footer(text="💡 `/티어상승`을 통해 포인트를 소모하여 티어를 올릴 수 있습니다!")

    # 메시지 전송
    await interaction.response.send_message(embed=embed)

# /배치고사 커맨드 (임베드 적용)
@bot.tree.command(name="배치고사", description="초기 티어를 부여받습니다.")
async def placement_test(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = load_user_data()

    if user_id in user_data and "tier" in user_data[user_id]:
        embed = discord.Embed(
            title="❌ 이미 배치고사를 완료하셨습니다!",
            description="배치고사는 한 번만 진행할 수 있습니다.",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    tier = assign_initial_tier()
    user_data[user_id] = {"tier": tier}
    save_user_data(user_data)

    tier_name = tier.split()[0]
    embed = discord.Embed(
        title="🏆 배치고사 결과",
        description=f"🎉 축하합니다! 당신의 초기 티어는 **{tier}** 입니다.",
        color=TIER_COLORS.get(tier_name, 0xFFFFFF)
    )
    embed.set_thumbnail(url=TIER_IMAGES.get(tier_name, "https://example.com/default.png"))
    await interaction.response.send_message(embed=embed, ephemeral=True)

# 포인트 차감 함수
def deduct_points(user_id, amount):
    data = load_points()
    if user_id in data and data[user_id] >= amount:
        data[user_id] -= amount
        save_points(data)
        return True
    return False

# 티어별 필요 포인트
def get_required_points(tier):
    tier_points = {
        "브론즈": 100000,
        "실버": 200000,
        "골드": 500000,
        "플래티넘": 1000000,
        "다이아몬드": 10000000,
        "마스터": 50000000,
        "그랜드마스터": 100000000,
    }
    tier_name = tier.split()[0]
    return tier_points.get(tier_name, 0)

# 티어상승 커맨드
@bot.tree.command(name="티어상승", description="포인트를 소모하여 티어를 상승시킵니다.")
async def upgrade_tier(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_data = load_user_data()
    points_data = load_points()

    if user_id not in user_data or "tier" not in user_data[user_id]:
        embed = discord.Embed(
            title="🚫 티어가 없습니다!",
            description="먼저 `/배치고사` 명령어를 사용하여 티어를 부여받아주세요.",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    current_tier = user_data[user_id]["tier"]

    # ✅ 최고 티어는 승급 불가
    if current_tier == "그랜드마스터":
        embed = discord.Embed(
            title="🏆 최고 티어 도달!",
            description="당신은 이미 **최고 티어**인 `그랜드마스터`입니다!\n더 이상 티어를 올릴 수 없습니다.",
            color=0xFFD700
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    required_points = get_required_points(current_tier)

    if user_id not in points_data or points_data[user_id] < required_points:
        embed = discord.Embed(
            title="❌ 포인트 부족!",
            description=f"티어 상승을 위해 **{required_points:,} 포인트**가 필요합니다.\n현재 보유 포인트: **{points_data.get(user_id, 0):,}**",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not deduct_points(user_id, required_points):
        embed = discord.Embed(
            title="⚠️ 포인트 차감 오류!",
            description="포인트 차감 중 오류가 발생했습니다. 다시 시도해 주세요.",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # ✅ 티어 변경 확인
    new_tier = tier_upgrade(current_tier)
    user_data[user_id]["tier"] = new_tier
    save_user_data(user_data)

    # 남은 포인트 업데이트
    remaining_points = points_data.get(user_id, 0)

    # ✅ 올바른 티어 비교 방식 적용
    def tier_to_numeric(tier_str):
        """ 티어 문자열을 숫자로 변환하여 비교 가능하도록 함 """
        tier_order = ["브론즈", "실버", "골드", "플래티넘", "다이아몬드", "마스터", "그랜드마스터"]
        parts = tier_str.split()
        tier_name = parts[0]
        tier_number = int(parts[1]) if len(parts) > 1 else 0  # 그랜드마스터는 숫자가 없음

        return (tier_order.index(tier_name), -tier_number)  # 숫자가 낮을수록 상위 티어

    old_rank = tier_to_numeric(current_tier)
    new_rank = tier_to_numeric(new_tier)

    if new_rank < old_rank:
        embed = discord.Embed(
            title="📉 티어 하락...",
            description=f"아쉽게도 티어가 하락했습니다.\n현재 티어: **{new_tier}**\n\n💰 남은 포인트: **{remaining_points:,}**",
            color=0xFF4500  # 빨간색 계열
        )
    else:
        embed = discord.Embed(
            title="✨ 티어 변경 완료!",
            description=f"당신의 새로운 티어는 **{new_tier}** 입니다.\n\n💰 남은 포인트: **{remaining_points:,}**",
            color=TIER_COLORS.get(new_tier.split()[0], 0xFFFFFF)
        )

    embed.set_thumbnail(url=TIER_IMAGES.get(new_tier.split()[0], "https://example.com/default.png"))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="도움말", description="도움말 페이지 링크를 확인합니다.")
async def help_link(interaction: discord.Interaction):
    help_url = "https://stupid-bot-help-page.vercel.app/"  # Vercel에서 배포된 링크
    await interaction.response.send_message(
        f"📖 [도움말 페이지를 확인하려면 여기를 클릭하세요]({help_url})"
    )

# 명령어 사용 로깅 기능
@bot.event
async def on_command(ctx):
    server_name = ctx.guild.name if ctx.guild else "DM"
    user_name = ctx.author.name
    command_name = ctx.command.name
    print(f"[Command Log] Server: {server_name} | User: {user_name} | Command: {command_name}")

# 모든 슬래시 명령어 실행 로그 출력
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        server = interaction.guild.name if interaction.guild else "DM"
        user = interaction.user.name
        command_name = interaction.data['name']
        print(f"[App Command Log] App Command | Server: {server} | User: {user} | Command: {command_name}")

        # 명령어 로그 이후 추가 동작
        await bot.process_application_commands(interaction)

async def main():
    async with bot:
        bot.remove_command("help")
        await bot.add_cog(Music(bot))
        await bot.add_cog(Utility(bot))
        await bot.add_cog(Game(bot))
        await bot.start(Token)
asyncio.run(main())