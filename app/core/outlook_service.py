import sys
# Force pywin32 to use dynamic/late-binding. This prevents the "wrong number of parameters"
# or "parameter error" on client PCs due to gen_py cached wrapper signatures mismatch.
sys.modules['win32com.gen_py'] = None
import win32com.client as win32
import os
import re
import uuid
import tempfile
import base64
import urllib.parse

class OutlookService:
    @staticmethod
    def is_outlook_available():
        """
        Checks if Outlook is installed and can be connected to via COM.
        Returns a tuple: (is_available, error_message)
        """
        try:
            # Attempt to dispatch Outlook.Application
            outlook = win32.Dispatch("Outlook.Application")
            # Try to access namespace to ensure it's fully functional
            _ = outlook.GetNamespace("MAPI")
            return True, ""
        except Exception as e:
            return False, str(e)

    @staticmethod
    def get_accounts():
        """
        Retrieves the list of Outlook email accounts.
        Returns a list of dicts: [{"display_name": str, "email": str}]
        """
        accounts = []
        try:
            outlook = win32.Dispatch("Outlook.Application")
            accounts_col = outlook.Session.Accounts
            for i in range(1, accounts_col.Count + 1):
                try:
                    acc = accounts_col.Item(i)
                    try:
                        email = acc.SmtpAddress
                    except AttributeError:
                        email = ""
                    
                    # Fallback to DisplayName if SmtpAddress is empty
                    if not email:
                        email = acc.DisplayName
                    
                    accounts.append({
                        "display_name": acc.DisplayName,
                        "email": email
                    })
                except Exception as e_item:
                    print(f"Error fetching account item {i}: {e_item}")
        except Exception as e:
            print(f"Error fetching Outlook accounts: {e}")
        return accounts

    @staticmethod
    def create_mail(to, cc, subject, html_body, sender_email=None, attachments=None, save_draft=True):
        """
        Creates and configures a mail item.
        Returns the COM mail object.
        """
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        
        # Set basic fields
        mail.To = to
        if cc:
            mail.CC = cc
        mail.Subject = subject
        
        # Clean MS Word VML markup to avoid broken images in Outlook
        style_prefix = "<style>p { margin-top: 0; margin-bottom: 12px; } table { border-collapse: collapse; } th, td { border: 1px solid #d1d1d6; padding: 6px; min-width: 30px; }</style>"
        cleaned_body = OutlookService.clean_vml_markup(html_body)
        full_html = style_prefix + cleaned_body
        
        # Embed inline images (attaches local/base64 images to the mail item)
        embedded_html = OutlookService.embed_images(mail, full_html)
        mail.HTMLBody = embedded_html

        # Set attachments if any
        if attachments:
            for path in attachments:
                mail.Attachments.Add(path)

        # Set SendUsingAccount if sender_email is provided
        if sender_email:
            found_account = False
            try:
                accounts_col = outlook.Session.Accounts
                for i in range(1, accounts_col.Count + 1):
                    acc = accounts_col.Item(i)
                    try:
                        email = acc.SmtpAddress
                    except AttributeError:
                        email = acc.DisplayName
                    
                    if email == sender_email or acc.DisplayName == sender_email:
                        try:
                            mail.SendUsingAccount = acc
                        except Exception:
                            try:
                                # Bypass win32com wrapper limitation using direct OLE Invoke with DISPID 64209
                                mail._oleobj_.Invoke(*(64209, 0, 8, 0, acc))
                            except Exception as e:
                                print(f"Error setting SendUsingAccount via OLE Invoke: {e}")
                        found_account = True
                        break
            except Exception as e:
                print(f"Error iterating accounts in create_mail: {e}")

        # Force Outlook to process the HTML, bind attachments, and save to Drafts if displaying
        if save_draft:
            try:
                _ = mail.GetInspector
                mail.Save()
            except Exception as e:
                print(f"Error initializing inspector and saving mail draft: {e}")

        return mail

    @staticmethod
    def clean_vml_markup(html):
        if not html:
            return html
        # Remove VML conditional blocks
        html = re.sub(r'<!--\[if gte vml 1\].*?<!\[endif\]-->', '', html, flags=re.DOTALL | re.IGNORECASE)
        # Remove VML conditional comment wrappers, keeping the standard tags inside
        html = re.sub(r'<!--\[if !vml\]-->', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<!--\[if !supportVML\]-->', '', html, flags=re.IGNORECASE)
        html = re.sub(r'<!--\[endif\]-->', '', html, flags=re.IGNORECASE)
        return html

    @staticmethod
    def embed_images(mail, html_body):
        """
        Parses html_body to find local file path images and base64 encoded images,
        saves base64 to temp files, attaches them to the Outlook mail item,
        sets PR_ATTACH_CONTENT_ID, and updates HTML src attributes to cid:unique_id.
        """
        if not html_body:
            return html_body

        # Regex to match <img> or VML <v:imagedata> tags and capture their src value
        img_pattern = re.compile(r'(<(?:img|v:imagedata)[^>]+src=["\'])([^"\']*)(["\'][^>]*>)', re.IGNORECASE)
        img_count = [0]

        def repl(match):
            prefix = match.group(1)
            src = match.group(2)
            suffix = match.group(3)

            # Skip web URLs or existing cid attachments
            if src.startswith("http://") or src.startswith("https://") or src.startswith("cid:"):
                return match.group(0)

            cid = f"img_{uuid.uuid4().hex[:8]}_{img_count[0]}"
            img_count[0] += 1

            # A. Base64 Image
            if src.startswith("data:image/"):
                try:
                    header, base64_data = src.split(",", 1)
                    ext = "png"
                    if "jpeg" in header or "jpg" in header:
                        ext = "jpg"
                    elif "gif" in header:
                        ext = "gif"

                    cid = f"img_{uuid.uuid4().hex[:8]}_{img_count[0]}.{ext}"
                    img_count[0] += 1

                    data = base64.b64decode(base64_data)
                    temp_dir = tempfile.gettempdir()
                    temp_path = os.path.join(temp_dir, cid)
                    
                    with open(temp_path, "wb") as f:
                        f.write(data)

                    # Attach the file and set MAPI property for CID matching the exact filename
                    attachment = mail.Attachments.Add(temp_path)
                    attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", cid)
                    attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x370E0003", 4) # ATT_MIME inline flag
                    try:
                        attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x7FFE000B", True) # Hide from well
                    except Exception:
                        pass
                    
                    return f"{prefix}cid:{cid}{suffix}"
                except Exception as e:
                    print(f"Error embedding base64 image: {e}")
                    return match.group(0)

            # B. Local Path Image
            else:
                file_path = src
                if file_path.startswith("file:///"):
                    file_path = file_path[8:]
                
                # Unquote URL encoding (%20 to space, etc.)
                file_path = urllib.parse.unquote(file_path)
                file_path = os.path.normpath(file_path)

                if os.path.exists(file_path):
                    try:
                        # Extract original extension
                        _, ext = os.path.splitext(file_path)
                        ext = ext.lstrip('.').lower() if ext else "png"
                        
                        cid = f"img_{uuid.uuid4().hex[:8]}_{img_count[0]}.{ext}"
                        img_count[0] += 1

                        # Attach the file
                        attachment = mail.Attachments.Add(file_path)
                        attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x3712001F", cid)
                        attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x370E0003", 4) # ATT_MIME inline flag
                        try:
                            attachment.PropertyAccessor.SetProperty("http://schemas.microsoft.com/mapi/proptag/0x7FFE000B", True) # Hide from well
                        except Exception:
                            pass
                        return f"{prefix}cid:{cid}{suffix}"
                    except Exception as e:
                        print(f"Error embedding local image {file_path}: {e}")
                        return match.group(0)
                else:
                    print(f"Image path does not exist on local disk: {file_path}")
                    return match.group(0)

        return img_pattern.sub(repl, html_body)

    @staticmethod
    def send_now(mail):
        """Sends the mail immediately in the background."""
        # 1. Resolve recipients for immediate delivery
        try:
            mail.Recipients.ResolveAll()
        except Exception:
            pass
            
        # 2. Dispatch Send. Catch programmatic access blocks
        try:
            mail.Send()
        except Exception as e:
            err_msg = str(e)
            if "2147024809" in err_msg or "매개 변수" in err_msg or "parameter is incorrect" in err_msg.lower():
                raise RuntimeError(
                    "아웃룩 백그라운드 발송이 차단되었습니다.\n"
                    "사유: 아웃룩의 '프로그램 방식 액세스 보안' 정책에 의해 타사 프로그램의 즉시 발송이 제한되었을 수 있습니다.\n\n"
                    "해결방법: 메일 기본 정보의 'Outlook에서 확인' 버튼을 클릭한 뒤, 아웃룩 창이 뜨면 직접 [보내기] 버튼을 눌러 발송해 주세요."
                ) from e
            raise e

    @staticmethod
    def display(mail):
        """Displays the Outlook Compose window for manual inspection."""
        mail.Display()
