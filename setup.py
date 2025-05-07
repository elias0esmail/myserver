#!/data/data/com.termux/files/usr/bin/python3

import os
import time
import shutil
import re
import subprocess
from pathlib import Path
import tempfile


def setup_apache_ssl():
    """إنشاء شهادات SSL مع إعدادات متقدمة وتهيئة ملف httpd-ssl.conf"""
    apache_dir = Path(os.environ['PREFIX']) / 'etc/apache2'
    ssl_conf_path = apache_dir / "extra/httpd-ssl.conf"
    cert_path = apache_dir / "server.crt"
    key_path = apache_dir / "server.key"
    document_root = "/data/data/com.termux/files/home/storage/shared/htdocs"

    if cert_path.exists() and key_path.exists():
        print("\033[1;33m Certificate already exists Skip creation \033[0m")
        return True

    temp_config_path = None  # تهيئة المتغير

    try:
        # إنشاء مجلد مؤقت ضمن بيئة Termux
        temp_dir = apache_dir / "tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # إنشاء ملف التكوين المؤقت
        openssl_config = """
        [req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no
default_bits = 2048
default_md = sha256

[req_distinguished_name]
C = US
ST = California
L = San Francisco
O = My Organization
OU = IT Department
CN = localhost

[v3_req]
basicConstraints = CA:FALSE
keyUsage = digitalSignature, keyEncipherment, nonRepudiation
extendedKeyUsage = serverAuth, clientAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = localhost.localdomain
IP.1 = 127.0.0.1
IP.2 = ::1
"""
        temp_config_path = temp_dir / "openssl_apache.cnf"
        
        with open(temp_config_path, "w") as f:
            f.write(openssl_config)

        # توليد الشهادة
        subprocess.run([
            "openssl", "req", "-x509", "-nodes", "-days", "365",
            "-newkey", "rsa:2048",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-config", str(temp_config_path)
        ], check=True)
        print("\033[1;32m SSL certificate created successfully \033[0m")

    except subprocess.CalledProcessError as e:
        print(f"\033[1;31m Error creating certificate {e}\033[0m")
        return False
    except Exception as e:
        print(f"\033[1;31m unexpected error {e}\033[0m")
        return False
    finally:
        # تنظيف الملف المؤقت إذا وُجد
        if temp_config_path and temp_config_path.exists():
            try:
                temp_config_path.unlink()
            except Exception as e:
                print(f"\033[1;33m Warning: Failed to delete temporary files. {e}\033[0m")

    # إنشاء ملف تكوين Apache
    ssl_conf_content = f"""\
Listen 8443

<VirtualHost *:8443>
    SSLEngine on
    SSLCertificateFile {cert_path}
    SSLCertificateKeyFile {key_path}
    SSLProtocol all -SSLv3 -TLSv1 -TLSv1.1
    SSLCipherSuite HIGH:!aNULL:!MD5
    SSLHonorCipherOrder on
    
    ServerAdmin admin@localhost
    DocumentRoot "{document_root}"
    
    <Directory "{document_root}">
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
</VirtualHost>
"""

    try:
        ssl_conf_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ssl_conf_path, "w") as f:
            f.write(ssl_conf_content)
        print("\033[1;32m httpd-ssl.conf file created successfully \033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m Error writing configuration file {e}\033[0m")
        return False

def create_htaccess():
    """إنشاء ملف .htaccess مع الإعدادات المطلوبة"""
    htaccess_path = Path("/data/data/com.termux/files/home/storage/shared/htdocs/.htaccess")
    content = """# Precedence is from left to right
# .php will be preferred
DirectoryIndex index.php index.html index.htm index2.html default.html default.htm"""

    try:
        htaccess_path.parent.mkdir(parents=True, exist_ok=True)
        with open(htaccess_path, 'w') as f:
            f.write(content)
        print("\033[1;32m .htaccess file created successfully \033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m Error creating .htaccess file {str(e)}\033[0m")
        return False

def modify_httpd_conf():
    """تعديل ملف httpd.conf لبيئة Termux"""
    apache_dir = Path(os.environ['PREFIX']) / 'etc/apache2'
    httpd_conf = apache_dir / 'httpd.conf'
    new_root = "/data/data/com.termux/files/home/storage/shared/htdocs"
    php_module_path = str(Path(os.environ['PREFIX']) / 'libexec/apache2/libphp.so')
    
    if not httpd_conf.exists():
        print("\033[1;31m httpd.conf does not exist error \033[0m")
        return False

    try:
        backup = httpd_conf.with_suffix('.bak')
        if not backup.exists():
            shutil.copy2(httpd_conf, backup)
            print("\033[1;33m A backup copy of the file has been created. \033[0m")
        
        with open(httpd_conf, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # تحديث DocumentRoot و Directory
        content = re.sub(
            r'^DocumentRoot\s+".*"',
            f'DocumentRoot "{new_root}"',
            content,
            flags=re.MULTILINE
        )
        content = re.sub(
            r'<Directory\s+".*">',
            f'<Directory "{new_root}">',
            content,
            flags=re.MULTILINE
        )
        
        # تبديل MPM modules
        content = re.sub(
            r'^LoadModule mpm_worker_module\b.*',
            '#LoadModule mpm_worker_module libexec/apache2/mod_mpm_worker.so',
            content,
            flags=re.MULTILINE
        )
        content = re.sub(
            r'^#LoadModule mpm_prefork_module\b.*',
            'LoadModule mpm_prefork_module libexec/apache2/mod_mpm_prefork.so',
            content,
            flags=re.MULTILINE
        )
        
        # تفعيل SSL
        content = re.sub(
            r'^#LoadModule ssl_module\b.*',
            'LoadModule ssl_module libexec/apache2/mod_ssl.so',
            content,
            flags=re.MULTILINE
        )
        
        ssl_include = f"Include {os.environ['PREFIX']}/etc/apache2/extra/httpd-ssl.conf"
        if ssl_include not in content:
            content += f"\n{ssl_include}\n"
        
        # إعدادات الدليل الجديد
        dir_config = f'''<Directory "{new_root}">
    Options Indexes FollowSymLinks
    AllowOverride All
    Require all granted
</Directory>'''
        
        if f'<Directory "{new_root}">' not in content:
            content += f"\n{dir_config}\n"
        
        # إعدادات PHP
        php_config = f"""
# PHP configuration
LoadModule php_module {php_module_path}
<FilesMatch \.php$>
    SetHandler application/x-httpd-php
</FilesMatch>
"""
        if "LoadModule php_module" not in content:
            content += php_config
        
        # تحديث DirectoryIndex
        content = re.sub(
            r'<IfModule dir_module>.*?DirectoryIndex\s+.*?</IfModule>',
            '<IfModule dir_module>\n    DirectoryIndex index.php index.html\n</IfModule>',
            content,
            flags=re.DOTALL
        )
        
        with open(httpd_conf, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("\033[1;32m Modified successfully \033[0m")
        return True
    
    except Exception as e:
        print(f"\033[1;31m Error while editing {str(e)}\033[0m")
        return False

def setup_htdocs():
    """إعداد مجلد htdocs الرئيسي"""
    try:
        new_root = Path("/data/data/com.termux/files/home/storage/shared/htdocs")
        new_root.mkdir(parents=True, exist_ok=True)
        os.chmod(new_root, 0o755)
        
        (new_root / "index.php").write_text("<?php echo '<h1>خادم PHP يعمل!</h1>';  ?>")
        
        phpinfo_dir = new_root / "phpinfo"
        phpinfo_dir.mkdir(exist_ok=True)
        (phpinfo_dir / "index.php").write_text("<?php phpinfo(); ?>")
        
        print("\033[1;32m htdocs folder created successfully \033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m Error setting htdocs folder {str(e)}\033[0m")
        return False

def install_phpmyadmin(htdocs_path):
    """تثبيت phpMyAdmin وتعديل إعدادات السماح بالدخول بدون كلمة مرور وتعديل المضيف"""
    try:
        pma_dir = htdocs_path / "phpmyadmin"
        
        # تثبيت phpMyAdmin إذا لم يكن موجوداً
        if not pma_dir.exists():
            os.chdir(htdocs_path)
            os.system("composer create-project -q phpmyadmin/phpmyadmin")
            print("\033[1;32m phpMyAdmin has been installed successfully. \033[0m")
        else:
            print("\033[1;33m phpmyadmin already exists skipping setup \033[0m")

        # التعامل مع ملف التكوين
        config_sample = pma_dir / "config.sample.inc.php"
        config_file = pma_dir / "config.inc.php"

        # إعادة تسمية الملف النموذجي إذا لزم الأمر
        if config_sample.exists():
            if not config_file.exists():
                try:
                    config_sample.rename(config_file)
                    print("\033[1;32m The configuration file has been renamed to config.inc.php. \033[0m")
                except Exception as e:
                    print(f"\033[1;31m Error renaming configuration file {e}\033[0m")
                    return False
            else:
                print("\033[1;33m The configuration file already exists. \033[0m")
        else:
            if not config_file.exists():
                print("\033[1;31m Configuration file not found \033[0m")
                return False

        # تعديل الإعدادات المطلوبة
        try:
            with open(config_file, 'r+') as f:
                original_content = content = f.read()
                
                # تعديل إعداد AllowNoPassword
                new_content = re.sub(
                    r"\$cfg\['Servers'\]\[\$i\]\['AllowNoPassword'\]\s*=\s*false;",
                    "$cfg['Servers'][$i]['AllowNoPassword'] = true;",
                    content
                )
                allow_no_password_modified = (new_content != content)
                
                # تعديل إعداد المضيف إلى 127.0.0.1
                new_content = re.sub(
                    r"(\$cfg\['Servers'\]\[\$i\]\['host'\]\s*=\s*)'localhost';",
                    r"\1'127.0.0.1';",
                    new_content
                )
                host_modified = (new_content != content)
                
                # حفظ التغييرات إذا وجدت
                if new_content != original_content:
                    f.seek(0)
                    f.write(new_content)
                    f.truncate()
                    messages = []
                    if allow_no_password_modified:
                        messages.append("Passwordless login enabled")
                    if host_modified:
                        messages.append("Server settings have been changed.")
                    print("\033[1;32m" + "، ".join(messages) + "\033[0m")
                else:
                    print("\033[1;33m Settings not found \033[0m")
            
            return True
        except Exception as e:
            print(f"\033[1;31m Error modifying configuration file {str(e)}\033[0m")
            return False

    except Exception as e:
        print(f"\033[1;31m phpMyAdmin installation error {str(e)}\033[0m")
        return False

def make_myserver_executable():
    """جعل ملف myserver قابل للتنفيذ"""
    source_path = Path.home() / "myserver" / "myserver"
    destination_path = Path(os.environ['PREFIX']) / 'bin' / "myserver"
    
    try:
        if not source_path.exists():
            print("\033[1;33m The file myserver does not exist. \033[0m")
            return True
        
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not os.access(source_path, os.X_OK):
            os.chmod(source_path, 0o755)
        
        shutil.copy(source_path, destination_path)
        os.chmod(destination_path, 0o755)
        
        if destination_path.exists():
            print("\033[1;32m Myserver file has been created successfully. \033[0m")
            return True
        else:
            print("\033[1;31m Failed to prepare the file \033[0m")
            return False
            
    except Exception as e:
        print(f"\033[1;31m An unexpected error occurred:{str(e)}\033[0m")
        return False

def create_php_ini():
    """إنشاء ملف php.ini مع الإعدادات المطلوبة"""
    php_ini_path = Path(os.environ['PREFIX']) / 'etc/php/php.ini'
    php_ini_content = """\
; إعدادات تحميل الملفات
upload_max_filesize = 2256M
post_max_size = 256M

; إعدادات الذاكرة والتنفيذ
memory_limit = 512M
max_execution_time = 180

; إعدادات عرض الأخطاء
error_reporting = E_ALL & ~E_DEPRECATED
display_errors = On
"""

    try:
        php_ini_path.parent.mkdir(parents=True, exist_ok=True)
        with open(php_ini_path, 'w') as f:
            f.write(php_ini_content)
        print("\033[1;32m The php.ini file was created successfully. \033[0m")
        return True
    except Exception as e:
        print(f"\033[1;31m Error creating php.ini file : {str(e)}\033[0m")
        return False

def main():
    try:
        print("\033[1;33mInstalling Myserver..\033[0m")
        
        steps = [
            ("Update packages", "pkg update -y && pkg upgrade -y"),
            ("Storage settings", None),
            ("Installing basic packages", "pkg install -y php-apache openssl-tool mariadb composer wget"),
            ("Configure SSL settings", setup_apache_ssl),
            ("Apache settings", modify_httpd_conf),
            ("Prepare htdocs folder", setup_htdocs),
            ("Create an .htaccess file", create_htaccess),
            ("Install phpMyAdmin", lambda: install_phpmyadmin(Path("/data/data/com.termux/files/home/storage/shared/htdocs"))),
            ("MyServer configuration settings", make_myserver_executable),
            ("Create php.ini file", create_php_ini),
            ("Validity settings", None)
        ]

        for i, (desc, action) in enumerate(steps, 1):
            print(f"\033[1;34m[{i}/11] Preparing {desc}...\033[0m")
            
            if desc == "Storage settings":
                if not Path("~/storage").expanduser().exists():
                    subprocess.run(
                        "termux-setup-storage",
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    time.sleep(5)
            
            elif desc == "Validity settings":
                htdocs_path = Path("/data/data/com.termux/files/home/storage/shared/htdocs")
                subprocess.run(
                    f"chmod 755 {htdocs_path} -R",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            
            elif callable(action):
                if not action():
                    raise Exception(f"Failed to  {desc}")
            
            else:
                if action:
                    subprocess.run(
                        action,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
        
        print("\n\033[1;32mmyserver has been installed successfully\033[0m")
        htdocs_path = Path("/data/data/com.termux/files/home/storage/shared/htdocs")
        print(f"\033[1;36m Main file path : {htdocs_path}")
        print("Server address: http://localhost:8080")
        print("Safe server address: https://localhost:8443")
        print("Type myserver to start Server")
        
    except Exception as e:
        print(f"\033[1;31mAn unexpected error: {str(e)}\033[0m")
        exit(1)

if __name__ == "__main__":
    main()