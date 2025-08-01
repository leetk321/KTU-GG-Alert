from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.ext import MessageHandler, filters
import asyncio
import json
from datetime import datetime, timedelta
from pytz import timezone
from functools import wraps

# JSON 파일 경로
DATA_FILE = "schedules.json"
HISTORY_FILE = "past_schedules.json"
USER_ID_FILE = "user_ids.json"  # 사용자 ID를 저장할 파일
MUTE_FILE = "mute_schedules.json"
ADMIN_FILE = "admins.json"  # 관리자 ID 저장 파일

# 시간대 설정 (한국 표준시)
KST = timezone("Asia/Seoul")

def load_admins():
    """JSON 파일에서 관리자 목록 불러오기."""
    try:
        with open(ADMIN_FILE, "r", encoding="utf-8") as file:
            return json.load(file)  # 관리자 목록 반환
    except FileNotFoundError:
        return []  # 파일이 없으면 빈 리스트 반환

def save_admins(admin_list):
    """관리자 목록을 JSON 파일에 저장."""
    with open(ADMIN_FILE, "w", encoding="utf-8") as file:
        json.dump(admin_list, file, ensure_ascii=False, indent=4)

ADMIN_PASSWORD = "0000"  # 설정할 관리자 비밀번호

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type
    admins = load_admins()

    # 단톡방에서 실행된 경우 안내 메시지 출력
    if chat_type in ["group", "supergroup"]:
        await update.message.reply_text(
             "❌ 개인 채팅에서만 사용 가능한 명령어입니다.\n단톡방에서는 [/adminroom 비밀번호 방이름] 을 사용해 방 전체에 관리 권한을 부여하세요."
        )
        return

    # 개인 채팅에서만 관리자 등록 가능
    if any(admin['chat_id'] == chat_id for admin in admins):
        await update.message.reply_text("✅ 이미 관리자로 등록된 계정입니다.")
        return

    # 비밀번호 요청 메시지
    context.user_data["admin_state"] = "awaiting_password"
    await update.message.reply_text("🔒 관리자 비밀번호를 입력하세요:")

async def adminroom_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """단톡방에 관리 권한을 부여하는 명령어."""
    chat_id = update.message.chat_id
    chat_type = update.message.chat.type
    args = context.args
    admins = load_admins()

    # 단톡방이 아닌 경우 처리
    if chat_type not in ["group", "supergroup"]:
        await update.message.reply_text("❌ 이 명령어는 단톡방에서만 사용할 수 있습니다.")
        return

    # 비밀번호 및 단톡방 이름 확인
    if len(args) < 2:
        await update.message.reply_text("❌ 명령어 형식이 올바르지 않습니다.\n예) /adminroom 비밀번호 방이름")
        return

    password, room_name = args[0], " ".join(args[1:])
    if password != ADMIN_PASSWORD:
        await update.message.reply_text("❌ 비밀번호가 올바르지 않습니다.")
        return

    # 이미 관리자인지 확인
    if any(admin['chat_id'] == chat_id for admin in admins):
        await update.message.reply_text(f"✅ 이미 단톡방에 관리 권한이 부여되어 있습니다.")
        return

    # 관리자 등록
    admins.append({"name": f"{room_name}(단톡방)", "chat_id": chat_id})
    save_admins(admins)
    await update.message.reply_text(f"✅ '{room_name}' 단톡방에 관리 권한을 부여하였습니다.")

async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    text = update.message.text.strip()
    admins = load_admins()

    # 비밀번호 확인 상태
    if context.user_data.get("admin_state") == "awaiting_password":
        if text == ADMIN_PASSWORD:
            context.user_data["admin_state"] = "awaiting_name"
            await update.message.reply_text("✅ 비밀번호가 확인되었습니다. 이름을 입력해주세요:")
        else:
            context.user_data.pop("admin_state", None)
            await update.message.reply_text("❌ 비밀번호가 올바르지 않습니다.")
    
    # 이름 입력 상태
    elif context.user_data.get("admin_state") == "awaiting_name":
        context.user_data.pop("admin_state", None)
        admin_name = text

        # 관리자 추가
        admins.append({"name": admin_name, "chat_id": chat_id})
        save_admins(admins)  # 관리자 목록 저장
        await update.message.reply_text(f"✅ {admin_name}님이 관리자로 등록되었습니다.")
    else:
        # 기타 입력은 fallback_handler로 처리
        await fallback_handler(update, context)

from functools import wraps

def admin_only(func):
    """관리자만 접근할 수 있도록 제한하는 데코레이터."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.message.chat_id
        admins = load_admins()  # 항상 최신 관리자 목록 불러오기

        # 관리자 목록에서 chat_id 확인
        if not any(admin['chat_id'] == chat_id for admin in admins):
            await update.message.reply_text("❌ 관리 권한이 필요한 기능입니다.")
            return

        # 관리자인 경우 함수 실행
        return await func(update, context, *args, **kwargs)

    return wrapper

@admin_only
async def admin_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 목록 출력."""
    admins = load_admins()

    if not admins:
        await update.message.reply_text("❌ 등록된 관리자가 없습니다.")
        return

    # 관리자 목록 출력
    response = "📋 관리자 목록:\n"
    for idx, admin in enumerate(admins, start=1):
        response += f"{idx}. {admin['name']}\n"

    await update.message.reply_text(response)

@admin_only
async def admin_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """관리자 삭제."""
    admins = load_admins()

    if not admins:
        await update.message.reply_text("❌ 삭제할 관리자가 없습니다.")
        return

    try:
        idx = int(context.args[0]) - 1  # 삭제할 관리자 번호
        if 0 <= idx < len(admins):
            deleted_admin = admins.pop(idx)
            save_admins(admins)
            await update.message.reply_text(f"✅ {deleted_admin['name']}님이 관리자에서 삭제되었습니다.")
        else:
            await update.message.reply_text("❌ 유효한 번호를 입력하세요.")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ 삭제할 번호를 올바르게 입력하세요.\n예) /admindel 1")

def load_mute_schedules():
    try:
        with open(MUTE_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))
    except FileNotFoundError:
        return set()  # 파일이 없으면 빈 집합 반환

def save_mute_schedules(mute_schedules):
    with open(MUTE_FILE, "w", encoding="utf-8") as file:
        json.dump(list(mute_schedules), file, ensure_ascii=False, indent=4)

def load_user_ids():
    try:
        with open(USER_ID_FILE, "r", encoding="utf-8") as file:
            return set(json.load(file))  # JSON에서 사용자 ID를 불러오기
    except FileNotFoundError:
        return set()  # 파일이 없으면 빈 집합 반환

def save_user_ids(user_ids):
    with open(USER_ID_FILE, "w", encoding="utf-8") as file:
        json.dump(list(user_ids), file, ensure_ascii=False, indent=4)  # 사용자 ID 저장

# 일정 데이터를 저장하고 불러오는 함수
def load_data(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return []  # 파일이 없으면 빈 리스트 반환

def save_data(file_path, data):
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

# 글로벌 변수 초기화
notified_schedules_hour = set()
notified_schedules_day = set()
notified_schedules_week = set()
global_schedule = load_data(DATA_FILE)
past_schedule = load_data(HISTORY_FILE)

# 프로그램 시작 시 mute 상태 불러오기
mute_schedules = load_mute_schedules()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if "user_ids" not in context.application.bot_data:
        context.application.bot_data["user_ids"] = load_user_ids()  # 파일에서 사용자 ID 불러오기
    user_ids = context.application.bot_data["user_ids"]

    if chat_id not in user_ids:
        user_ids.add(chat_id)  # 사용자 ID 추가
        save_user_ids(user_ids)  # 파일에 저장

    await update.message.reply_text(
        "안녕하세요! 전교조 경기지부 일정 알림 봇입니다.\n도움말을 보시려면 /help 를 입력하세요.\n\n🔔 [알림] 3시간 전, 하루 전, 일주일 전"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_message = (
        "📖 **일정 알림 봇 사용법**\n\n"
        "1️⃣ **일정 목록 보기**\n"
        "`/list`\n"
        "등록된 모든 일정을 확인합니다.\n\n"
        "2️⃣ **지난 일정 보기**\n"
        "`/history`\n"
        "지난 30일 간의 일정을 확인합니다.\n\n"
        "`/history365`\n"
        "지난 1년 간의 일정을 확인합니다.\n\n"
        "🔔 **알림**\n"
        "3시간 전, 하루 전, 일주일 전 알림 발송\n\n"
        "=======================\n\n"
        "⚠️ 관리자 전용 기능입니다.\n\n"
        "3️⃣ **공지사항 보내기**\n"
        "`/noti 공지내용`\n"
        "봇 사용자에게 공지사항을 보냅니다.\n"
        "예) `/noti 오늘 오후 3시에 회의가 있습니다.`\n\n"
        "`/adminnoti 내용`\n"
        "등록된 관리자에게만 공지를 보냅니다.\n"
        "예) `/adminnoti 오늘 5시에 회의가 있습니다.`\n\n"
        "4️⃣ **일정 추가**\n"
        "`/add YYMMDD HHMM 내용`\n"
        "예) `/add 241225 0900 성탄절`\n\n"
        "5️⃣ **일정 수정**\n"
        "`/edit 번호 YYMMDD HHMM 내용`\n"
        "예) `/edit 3 241231 1800 송년회`\n\n"
        "6️⃣ **일정 삭제**\n"
        "`/del 번호`\n"
        "예) `/del 4`\n\n"
        "7️⃣ **모든 일정 삭제**\n"
        "`/delall`\n"
        "모든 일정을 삭제합니다.\n\n"
        "8️⃣ **지난 일정 초기화**\n"
        "`/delhistory`\n"
        "저장된 과거 일정을 모두 삭제합니다.\n\n"
        "9️⃣ **알림 음소거**\n"
        "`/mute 번호`\n"
        "해당 일정의 알림을 음소거합니다.\n"
        "`/unmute 번호`\n"
        "해당 일정의 알림 음소거를 해제합니다.\n"
        "예) `/mute 4 (음소거 해제는 /unmute)`\n\n"
        "1️⃣0️⃣ **사용자 수 확인**\n"
        "`/user`\n"
        "등록된 사용자 수를 확인합니다. (관리자 전용)\n\n"
        "🔑 **관리자 설정 명령어**\n"
        "· 관리자 추가(개인)\n/admin → 비밀번호 입력 → 이름 입력\n"
        "· 관리자 추가(단톡)\n/adminroom 비밀번호 방이름\n"
        "· 명단 확인 : /adminlist, 삭제 : /admindel 번호\n"
    )
    await update.message.reply_text(help_message, parse_mode="Markdown")

@admin_only
async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        date_time = " ".join(args[:2])  # 날짜 및 시간
        description = " ".join(args[2:])  # 일정 내용
        event_time = KST.localize(datetime.strptime(date_time, "%y%m%d %H%M"))

        if event_time < datetime.now(KST):
            await update.message.reply_text("❌ 과거의 일정은 추가할 수 없습니다.")
            return

        global_schedule.append({"time": event_time.strftime("%y%m%d %H%M"), "description": description})
        save_data(DATA_FILE, global_schedule)
        
        # 요일을 한글로 변환
        day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
        day_of_week = day_of_week_map[event_time.strftime("%a")]

        am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"
        formatted_time = event_time.strftime(f"%y/%m/%d({day_of_week}) {am_pm_korean} %I:%M")

        await update.message.reply_text(f"✅ 새 일정이 추가되었습니다\n일정: {description}\n일시: {formatted_time}")
    except Exception:
        await update.message.reply_text("❌ 일정을 추가할 수 없습니다. 올바른 형식인지 확인하세요.\n예) /add 241231 1500 새해맞이 준비")

@admin_only
async def edit_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        global global_schedule, mute_schedules

        args = context.args
        if len(args) < 4:
            await update.message.reply_text("❌ 명령어 형식이 올바르지 않습니다.\n예) /edit [번호] [YYMMDD HHMM] [내용]")
            return

        # 수정할 일정의 인덱스
        idx = int(args[0]) - 1  # 사용자는 1부터 시작, 리스트는 0부터 시작
        date_time = " ".join(args[1:3])  # 새로운 날짜 및 시간
        description = " ".join(args[3:])  # 새로운 일정 내용
        event_time = KST.localize(datetime.strptime(date_time, "%y%m%d %H%M"))

        # 과거 시간으로 수정 시 오류 처리
        if event_time < datetime.now(KST):
            await update.message.reply_text("❌ 과거의 일정으로 수정할 수 없습니다.")
            return

        # 정렬된 일정 가져오기
        sorted_schedules = sorted(global_schedule, key=lambda x: datetime.strptime(x["time"], "%y%m%d %H%M"))

        # 유효한 인덱스 확인
        if 0 <= idx < len(sorted_schedules):
            original_event = sorted_schedules[idx]
            original_id = original_event["time"] + "_" + original_event["description"]  # 기존 고유 ID

            # 새 고유 ID 생성
            new_id = event_time.strftime("%y%m%d %H%M") + "_" + description

            # 일정 수정
            original_event["time"] = event_time.strftime("%y%m%d %H%M")
            original_event["description"] = description

            # mute 상태 업데이트
            if original_id in mute_schedules:
                mute_schedules.remove(original_id)  # 기존 ID 제거
                mute_schedules.add(new_id)         # 새 ID 추가

            # 데이터 저장
            save_data(DATA_FILE, global_schedule)

            # 요일 및 시간 변환
            day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
            day_of_week = day_of_week_map[event_time.strftime("%a")]
            am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"
            formatted_time = event_time.strftime(f"%y/%m/%d({day_of_week}) {am_pm_korean} %I:%M")

            await update.message.reply_text(f"✅ 일정이 수정되었습니다\n일정: {description}\n일시: {formatted_time}")
        else:
            await update.message.reply_text("❌ 유효한 번호를 입력하세요.")
    except ValueError:
        await update.message.reply_text("❌ 번호는 숫자로 입력해야 합니다.")
    except Exception:
        await update.message.reply_text(f"❌ 일정을 수정할 수 없습니다. 올바른 형식인지 확인하세요.\n예) /edit 3 241231 1500 새해맞이 준비")

async def view_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(KST)
    thirty_days_ago = now - timedelta(days=30)

    # 과거 일정 로드
    if not past_schedule:
        await update.message.reply_text("🔍 저장된 과거 일정이 없습니다.")
        return

    # 지난 30일 간의 일정 필터링
    try:
        recent_events = [
            {"time": item["time"], "description": item["description"]}
            for item in past_schedule
            if thirty_days_ago <= KST.localize(datetime.strptime(item["time"], "%y%m%d %H%M")) < now
        ]

        if recent_events:
            response = "📅 지난 30일 간의 일정:\n"
            for i, event in enumerate(recent_events, start=1):
                event_time = KST.localize(datetime.strptime(event["time"], "%y%m%d %H%M"))
                day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
                day_of_week = day_of_week_map[event_time.strftime("%a")]

                am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"

                # 날짜 형식 결정: 현재 연도와 같으면 MM/DD, 다르면 YY/MM/DD
                if event_time.year == now.year:
                    formatted_date = event_time.strftime("%m/%d")  # MM/DD
                else:
                    formatted_date = event_time.strftime("%y/%m/%d")  # YY/MM/DD

                formatted_time = f"{formatted_date}({day_of_week}) {am_pm_korean} {event_time.strftime('%I:%M')}"
                response += f"{i}. {formatted_time} - {event['description']}\n"
        else:
            response = "🔍 지난 30일 간의 일정이 없습니다."

    except Exception as e:
        response = f"❌ 오류 발생: {e}"

    await update.message.reply_text(response)

async def view_history_365(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(KST)
    thirty_days_ago = now - timedelta(days=365)

    # 과거 일정 로드
    if not past_schedule:
        await update.message.reply_text("🔍 저장된 과거 일정이 없습니다.")
        return

    # 지난 1년 간의 일정 필터링
    try:
        recent_events = [
            {"time": item["time"], "description": item["description"]}
            for item in past_schedule
            if thirty_days_ago <= KST.localize(datetime.strptime(item["time"], "%y%m%d %H%M")) < now
        ]

        if recent_events:
            response = "📅 지난 1년 간의 일정:\n"
            for i, event in enumerate(recent_events, start=1):
                event_time = KST.localize(datetime.strptime(event["time"], "%y%m%d %H%M"))
                day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
                day_of_week = day_of_week_map[event_time.strftime("%a")]

                am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"

                # 날짜 형식 결정: 현재 연도와 같으면 MM/DD, 다르면 YY/MM/DD
                if event_time.year == now.year:
                    formatted_date = event_time.strftime("%m/%d")  # MM/DD
                else:
                    formatted_date = event_time.strftime("%y/%m/%d")  # YY/MM/DD

                formatted_time = f"{formatted_date}({day_of_week}) {am_pm_korean} {event_time.strftime('%I:%M')}"
                response += f"{i}. {formatted_time} - {event['description']}\n"
        else:
            response = "🔍 지난 1년 간의 일정이 없습니다."

    except Exception as e:
        response = f"❌ 오류 발생: {e}"

    await update.message.reply_text(response)

@admin_only
async def mute_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0]) - 1
        sorted_schedules = sorted(global_schedule, key=lambda x: datetime.strptime(x["time"], "%y%m%d %H%M"))

        if 0 <= idx < len(sorted_schedules):
            schedule_id = sorted_schedules[idx]["time"] + "_" + sorted_schedules[idx]["description"]
            mute_schedules.add(schedule_id)
            save_mute_schedules(mute_schedules)  # 상태 저장
            await update.message.reply_text(f"✅ 일정이 음소거 처리되었습니다:\n{sorted_schedules[idx]['description']}")
        else:
            await update.message.reply_text("❌ 유효한 번호를 입력하세요.")
    except ValueError:
        await update.message.reply_text("❌ 번호는 숫자로 입력해야 합니다.")
    except Exception:
        await update.message.reply_text(f"❌ 음소거 처리 중 오류가 발생했습니다. 올바른 형식인지 확인하세요.\n예) /mute 4")

@admin_only
async def unmute_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0]) - 1
        sorted_schedules = sorted(global_schedule, key=lambda x: datetime.strptime(x["time"], "%y%m%d %H%M"))

        if 0 <= idx < len(sorted_schedules):
            schedule_id = sorted_schedules[idx]["time"] + "_" + sorted_schedules[idx]["description"]
            if schedule_id in mute_schedules:
                mute_schedules.remove(schedule_id)
                save_mute_schedules(mute_schedules)  # 상태 저장
                await update.message.reply_text(f"✅ 일정이 음소거 해제 처리되었습니다:\n{sorted_schedules[idx]['description']}")
            else:
                await update.message.reply_text("❌ 해당 일정은 음소거 상태가 아닙니다.")
        else:
            await update.message.reply_text("❌ 유효한 번호를 입력하세요.")
    except ValueError:
        await update.message.reply_text("❌ 번호는 숫자로 입력해야 합니다.")
    except Exception:
        await update.message.reply_text(f"❌ 음소거 처리 중 오류가 발생했습니다. 올바른 형식인지 확인하세요.\n예) /unmute 4")

async def list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not global_schedule:
        await update.message.reply_text("❌ 일정이 없습니다.")
        return

    # 일정 시간 순으로 정렬
    sorted_schedules = sorted(global_schedule, key=lambda x: datetime.strptime(x["time"], "%y%m%d %H%M"))

    message = "📅 등록된 일정:\n"
    for idx, schedule in enumerate(sorted_schedules, start=1):
        event_time = datetime.strptime(schedule["time"], "%y%m%d %H%M")
        day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
        day_of_week = day_of_week_map[event_time.strftime("%a")]

        am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"

        # 날짜 형식 결정: 현재 연도와 같으면 MM/DD, 다르면 YY/MM/DD
        now = datetime.now()
        if event_time.year == now.year:
            formatted_date = event_time.strftime("%m/%d")  # MM/DD
        else:
            formatted_date = event_time.strftime("%y/%m/%d")  # YY/MM/DD

        formatted_time = f"{formatted_date}({day_of_week}) {am_pm_korean} {event_time.strftime('%I:%M')}"
        
        # mute 여부 확인
        schedule_id = schedule["time"] + "_" + schedule["description"]
        mute_icon = "*" if schedule_id in mute_schedules else ""

        message += f"{idx}. {formatted_time} - {mute_icon}{schedule['description']}\n"

    # mute 기능 설명 추가
    message += "\n* : 알림이 울리지 않도록 설정된 일정"
    await update.message.reply_text(message)

@admin_only
async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        idx = int(context.args[0]) - 1  # 삭제할 일정 번호
        sorted_schedules = sorted(global_schedule, key=lambda x: datetime.strptime(x["time"], "%y%m%d %H%M"))

        if 0 <= idx < len(sorted_schedules):
            deleted = sorted_schedules[idx]
            global_schedule.remove(deleted)
            save_data(DATA_FILE, global_schedule)
            event_time = datetime.strptime(deleted["time"], "%y%m%d %H%M")

            day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
            day_of_week = day_of_week_map[event_time.strftime("%a")]

            am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"
            formatted_time = event_time.strftime(f"%y/%m/%d({day_of_week}) {am_pm_korean} %I:%M")

            await update.message.reply_text(f"✅ 일정이 삭제되었습니다\n일정: {deleted['description']}\n일시: {formatted_time}")
        else:
            await update.message.reply_text("❌ 유효한 번호를 입력하세요.\n예) /del 1")
    except Exception:
        await update.message.reply_text("❌ 일정 삭제 중 오류가 발생했습니다.")

async def update_schedule():
    global global_schedule, past_schedule
    now = datetime.now(KST)  # KST 시간대의 현재 시간
    updated_schedule = []

    for event in global_schedule:
        # event_time을 KST 시간대로 변환
        event_time = KST.localize(datetime.strptime(event["time"], "%y%m%d %H%M"))
        
        # 시간 비교 시 같은 시간대 객체로 비교
        if event_time < now:
            past_schedule.append(event)
        else:
            updated_schedule.append(event)

    global_schedule = updated_schedule
    save_data(DATA_FILE, global_schedule)
    save_data(HISTORY_FILE, past_schedule)

async def notify_schedules(application: Application):
    print("🔄 notify_schedules 태스크 시작")
    while True:
        try:
            now = datetime.now(KST)
            user_ids = application.bot_data.get("user_ids", [])
            print(f"현재 시간: {now}, 알림 대상 사용자 IDs: {set(user_ids)}")

            if not user_ids:
                await asyncio.sleep(60)
                continue

            for schedule in global_schedule[:]:
                event_time = KST.localize(datetime.strptime(schedule["time"], "%y%m%d %H%M"))
                description = schedule["description"]
                schedule_id = schedule["time"] + "_" + description  # 고유 ID 생성

                # Mute된 일정은 알림 제외
                if schedule_id in mute_schedules:
                    continue

                time_diff = event_time - now
                unique_id_hour = f"{event_time.strftime('%y%m%d %H%M')}_{description}_hour"
                unique_id_day = f"{event_time.strftime('%y%m%d %H%M')}_{description}_day"
                unique_id_week = f"{event_time.strftime('%y%m%d %H%M')}_{description}_week"

                day_of_week_map = {"Mon": "월", "Tue": "화", "Wed": "수", "Thu": "목", "Fri": "금", "Sat": "토", "Sun": "일"}
                day_of_week = day_of_week_map[event_time.strftime("%a")]
                am_pm_korean = "오전" if event_time.strftime("%p") == "AM" else "오후"
                formatted_time = event_time.strftime(f"%y/%m/%d({day_of_week}) {am_pm_korean} %I:%M").lstrip('0').replace(' 0', ' ')

                # 로그 출력: 이벤트 시간 및 남은 시간
                print(f"이벤트 시간: {event_time}, 남은 시간: {time_diff}")

                if time_diff <= timedelta(minutes=180) and time_diff > timedelta(minutes=179):
                    if unique_id_hour not in notified_schedules_hour:
                        for chat_id in user_ids:
                            try:
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🔔 [3시간 전 알림]\n일정: {description}\n시간: {formatted_time}"
                                )
                                print(f"🔔 [3시간 전 알림] - {description}, {formatted_time} - 알림이 발송됨")
                            except Exception as e:
                                print(f"❌ 알림 전송 실패 (3시간 전): {chat_id}, {e}")
                        notified_schedules_hour.add(unique_id_hour)

                if time_diff <= timedelta(days=1) and time_diff > timedelta(hours=23):
                    if unique_id_day not in notified_schedules_day:
                        for chat_id in user_ids:
                            try:
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🔔 [하루 전 알림]\n일정: {description}\n시간: {formatted_time}"
                                )
                                print(f"🔔 [하루 전 알림] - {description}, {formatted_time} - 알림이 발송됨")
                            except Exception as e:
                                print(f"❌ 알림 전송 실패 (하루 전): {chat_id}, {e}")
                        notified_schedules_day.add(unique_id_day)

                if time_diff <= timedelta(weeks=1) and time_diff > timedelta(days=6):
                    if unique_id_week not in notified_schedules_week:
                        for chat_id in user_ids:
                            try:
                                await application.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"🔔 [일주일 전 알림]\n일정: {description}\n시간: {formatted_time}"
                                )
                                print(f"🔔 [일주일 전 알림] - {description}, {formatted_time} - 알림이 발송됨")
                            except Exception as e:
                                print(f"❌ 알림 전송 실패 (일주일 전): {chat_id}, {e}")
                        notified_schedules_week.add(unique_id_week)

            # 이벤트별 체크 완료 후 로그 출력
            print("✅ 알림 체크 완료")

            await asyncio.sleep(60)  # 1분마다 실행
        except Exception as e:
            print(f"❌ notify_schedules 예외 발생: {e}")
            await asyncio.sleep(60)

@admin_only
async def user_count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """등록된 사용자 수를 알려주는 명령어 (관리자 전용)."""
    user_ids = context.application.bot_data.get("user_ids", set())
    count = len(user_ids)
    await update.message.reply_text(f"👥 현재 등록된 사용자는 총 {count}명입니다.")

@admin_only
async def notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 메시지 전체 텍스트에서 "/noti " 명령어 이후의 텍스트 추출
        message_text = update.message.text

        # "/noti"만 입력했거나 그 뒤에 아무 내용이 없을 경우 방어 처리
        if not message_text or not message_text.strip() or message_text.strip() == "/noti":
            await update.message.reply_text("❌ 공지 내용을 입력하세요.\n예) /noti 오늘 오후 3시에 회의가 있습니다.")
            return

        # 공지 내용 추출 (명령어 제거)
        notice_message = message_text[5:].strip()

        if not notice_message:  # 공백만 남았을 경우
            await update.message.reply_text("❌ 공지 내용을 입력하세요.\n예) /noti 오늘 오후 3시에 회의가 있습니다.")
            return

        # 사용자 ID 목록 불러오기
        user_ids = context.application.bot_data.get("user_ids", set())
        if not user_ids:
            await update.message.reply_text("❌ 알림을 보낼 대상이 없습니다.")
            return

        # 오류가 발생한 사용자 ID를 저장할 리스트
        failed_users = []

        # 각 사용자에게 메시지 전송
        for chat_id in list(user_ids):  # 리스트 복사본 사용
            try:
                await context.bot.send_message(chat_id=chat_id, text=f"📢 알림:\n\n{notice_message}")
            except Exception as e:
                error_message = str(e)
                # 그룹이 슈퍼그룹으로 마이그레이션된 경우 chat_id 업데이트
                if "migrated to supergroup" in error_message and "New chat id" in error_message:
                    import re
                    match = re.search(r"New chat id: (-?\d+)", error_message)
                    if match:
                        new_chat_id = int(match.group(1))
                        user_ids.remove(chat_id)
                        user_ids.add(new_chat_id)
                        save_user_ids(user_ids)
                        await update.message.reply_text(f"ℹ️ 그룹 chat_id가 변경되어 {new_chat_id}로 갱신하였습니다.")
                        continue
                failed_users.append(chat_id)
                user_ids.remove(chat_id)
                await update.message.reply_text(f"❌ 사용자 {chat_id}에게 메시지 전송 실패: {e}")

        # 사용자 데이터 업데이트
        save_user_ids(user_ids)
        success_count = len(user_ids)

        # 결과 메시지 출력
        if failed_users:
            await update.message.reply_text(
                f"⚠️ 차단 등으로 {len(failed_users)}개 대상에 메시지 전송 실패.\n"
                f"사용자 목록에서 삭제하였습니다.\n"
                f"✅ 공지사항이 모든 사용자({success_count}명)에게 전송되었습니다."
            )
        else:
            await update.message.reply_text(f"✅ 공지사항이 모든 사용자({success_count}명)에게 전송되었습니다.")

    except Exception as e:
        await update.message.reply_text(f"❌ 공지사항 전송 중 예상치 못한 오류가 발생했습니다: {e}")

# 관리자에게만 공지 전송하는 /adminnoti 명령어
@admin_only
async def admin_notice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 메시지 전체 텍스트에서 "/adminnoti " 명령어 이후의 텍스트 추출
        message_text = update.message.text

        # "/adminnoti"만 입력했거나 그 뒤에 아무 내용이 없을 경우 방어 처리
        if not message_text or not message_text.strip() or message_text.strip() == "/adminnoti":
            await update.message.reply_text("❌ 공지 내용을 입력하세요.\n예) /adminnoti 긴급 관리자 회의가 있습니다.")
            return

        # 공지 내용 추출 (명령어 제거)
        notice_message = message_text[10:].strip()

        if not notice_message:
            await update.message.reply_text("❌ 공지 내용을 입력하세요.\n예) /adminnoti 긴급 관리자 회의가 있습니다.")
            return

        # 관리자 목록 불러오기
        admins = load_admins()
        if not admins:
            await update.message.reply_text("❌ 등록된 관리자가 없습니다.")
            return

        # 실패한 관리자 목록 저장
        failed_admins = []

        # 각 관리자에게 메시지 전송
        for admin in admins:
            chat_id = admin["chat_id"]
            try:
                await context.bot.send_message(chat_id=chat_id, text=f"📢 관리자용 알림:\n\n{notice_message}")
            except Exception as e:
                error_message = str(e)
                # 그룹이 슈퍼그룹으로 마이그레이션된 경우 chat_id 업데이트
                if "migrated to supergroup" in error_message and "New chat id" in error_message:
                    import re
                    match = re.search(r"New chat id: (-?\d+)", error_message)
                    if match:
                        new_chat_id = int(match.group(1))
                        admin["chat_id"] = new_chat_id
                        save_admins(admins)
                        await update.message.reply_text(f"ℹ️ 관리자 chat_id가 변경되어 {new_chat_id}로 갱신하였습니다.")
                        continue
                failed_admins.append(chat_id)
                await update.message.reply_text(f"❌ 관리자 {chat_id}에게 메시지 전송 실패: {e}")

        # 결과 메시지 출력
        success_count = len(admins) - len(failed_admins)

        if failed_admins:
            await update.message.reply_text(
                f"⚠️ 일부 관리자에게 메시지 전송 실패 ({len(failed_admins)}명).\n"
                f"✅ 공지사항이 관리자 {success_count}명에게 전송되었습니다."
            )
        else:
            await update.message.reply_text(f"✅ 공지사항이 모든 관리자({success_count}명)에게 전송되었습니다.")

    except Exception as e:
        await update.message.reply_text(f"❌ 관리자 공지사항 전송 중 오류가 발생했습니다: {e}")

@admin_only
async def delall_confirm_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # 기존 작업이 진행 중인지 확인
    if f"confirm_action_{chat_id}" in context.application.bot_data:
        await update.message.reply_text("❌ 이전 확인 작업이 진행 중입니다.\n/ok 를 입력하거나 30초 후 다시 시도하세요.")
        return

    # 확인 작업 설정
    context.application.bot_data[f"confirm_action_{chat_id}"] = "delall"
    context.application.bot_data[f"confirm_task_{chat_id}"] = asyncio.create_task(confirm_timeout(chat_id, context))
    await update.message.reply_text(
        "⚠️ 모든 일정을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.\n확인하려면 /ok 를 입력하세요.\n\n⏳ 30초 이내로 응답하지 않으면 작업이 취소됩니다."
    )

@admin_only
async def delhistory_confirm_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # 기존 작업이 진행 중인지 확인
    if f"confirm_action_{chat_id}" in context.application.bot_data:
        await update.message.reply_text("❌ 이전 확인 작업이 진행 중입니다.\n/ok 를 입력하거나 30초 후 다시 시도하세요.")
        return

    # 확인 작업 설정
    context.application.bot_data[f"confirm_action_{chat_id}"] = "delhistory"
    context.application.bot_data[f"confirm_task_{chat_id}"] = asyncio.create_task(confirm_timeout(chat_id, context))
    await update.message.reply_text(
        "⚠️ 과거 일정을 초기화하시겠습니까?\n이 작업은 되돌릴 수 없습니다.\n확인하려면 /ok 를 입력하세요.\n\n⏳ 30초 이내로 응답하지 않으면 작업이 취소됩니다."
    )

async def confirm_timeout(chat_id, context):
    await asyncio.sleep(30)
    if context.application.bot_data.get(f"confirm_action_{chat_id}"):
        context.application.bot_data.pop(f"confirm_action_{chat_id}", None)
        context.application.bot_data.pop(f"confirm_task_{chat_id}", None)
        await context.bot.send_message(chat_id=chat_id, text="❌ 시간이 초과되어 작업이 취소되었습니다.")

# 확인 명령어 처리
async def ok_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # 확인 상태 가져오기
    confirm_action = context.application.bot_data.pop(f"confirm_action_{chat_id}", None)

    # 타이머 취소
    confirm_task = context.application.bot_data.pop(f"confirm_task_{chat_id}", None)
    if confirm_task:
        confirm_task.cancel()

    if confirm_action == "delall":
        global global_schedule
        global_schedule = []  # 모든 일정 삭제
        save_data(DATA_FILE, global_schedule)
        await update.message.reply_text("✅ 모든 일정이 삭제되었습니다.")
    elif confirm_action == "delhistory":
        global past_schedule
        past_schedule = []  # 과거 일정 초기화
        save_data(HISTORY_FILE, past_schedule)
        await update.message.reply_text("✅ 과거 일정이 초기화되었습니다.")
    else:
        await update.message.reply_text("❌ 확인할 작업이 없습니다.")

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 채팅 유형 확인 (private: 개인 채팅, group/supergroup: 단톡방)
    chat_type = update.message.chat.type

    if chat_type == "private":
        # 개인 채팅일 경우 /help 메시지 출력
        help_message = (
            "⚠️ 봇을 이용하려면 명령어를 입력해야 합니다.\n"
            "=======================\n\n"
            "🔔 **일정 알림 봇 사용법**\n\n"
            "1️⃣ **일정 목록 보기**\n"
            "`/list`\n"
            "등록된 모든 일정을 확인합니다.\n\n"
            "2️⃣ **지난 일정 보기**\n"
            "`/history`\n"
            "지난 30일 간의 일정을 확인합니다.\n\n"
            "📖 더 많은 기능은 /help를 참고하세요."
        )
        await update.message.reply_text(help_message, parse_mode="Markdown")

    elif chat_type in ["group", "supergroup"]:
        # 단톡방 메시지는 무시
        return

async def periodic_update_schedule():
    print("🔄 periodic_update_schedule 태스크 시작")
    while True:
        try:
            await update_schedule()
            await asyncio.sleep(60)  # 1분마다 실행
        except Exception as e:
            print(f"❌ periodic_update_schedule 예외 발생: {e}")
            await asyncio.sleep(60)

async def start_scheduler(application: Application):
    asyncio.create_task(notify_schedules(application))
    asyncio.create_task(periodic_update_schedule())

async def shutdown(application: Application):
    print("🔄 종료 처리 중...")

    # mute 상태 저장
    save_mute_schedules(mute_schedules)

    # 관리자 목록 저장
    admins = load_admins()  # 현재 메모리에서 로드
    save_admins(admins)  # JSON 파일에 저장
    print("✅ 관리자 목록이 저장되었습니다.")

    # 모든 비동기 태스크 취소
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    print("✅ 모든 태스크가 종료되었습니다.")


def main():
    application = Application.builder().token("TOKEN").build()     #TOKEN 지우고 토큰 번호 입력

    # 기존 사용자 ID를 불러오기
    application.bot_data["user_ids"] = load_user_ids()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_schedule))         # 관리자 전용
    application.add_handler(CommandHandler("list", list_schedules))
    application.add_handler(CommandHandler("edit", edit_schedule))         # 관리자 전용
    application.add_handler(CommandHandler("del", delete_schedule))         # 관리자 전용
    application.add_handler(CommandHandler("history", view_history))
    application.add_handler(CommandHandler("history365", view_history_365))
    application.add_handler(CommandHandler("noti", notice))         # 관리자 전용
    application.add_handler(CommandHandler("delall", delall_confirm_prompt))         # 관리자 전용
    application.add_handler(CommandHandler("delhistory", delhistory_confirm_prompt))         # 관리자 전용
    application.add_handler(CommandHandler("ok", ok_handler))  # /ok 핸들러 등록
    application.add_handler(CommandHandler("mute", mute_schedule))         # 관리자 전용
    application.add_handler(CommandHandler("unmute", unmute_schedule))         # 관리자 전용

    application.add_handler(CommandHandler("admin", admin_command))  # 관리자 인증
    application.add_handler(CommandHandler("adminroom", adminroom_command))  # 단톡방 관리자 등록
    application.add_handler(CommandHandler("adminlist", admin_list_command))  # 관리자 목록 조회
    application.add_handler(CommandHandler("admindel", admin_delete_command))  # 관리자 삭제
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))  # 비밀번호 및 이름 입력 처리

    application.add_handler(CommandHandler("user", user_count_command)) #유저수 확인
    application.add_handler(CommandHandler("adminnoti", admin_notice)) #관리자용 공지

    # 모든 텍스트 메시지 처리
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler))

    application.post_init = start_scheduler

    try:
        application.run_polling()
    except KeyboardInterrupt:
        asyncio.run(shutdown(application))

if __name__ == "__main__":
    main()