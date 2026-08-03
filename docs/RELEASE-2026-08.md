# one2one — 2026-08 Release Manifest (all tools + techstack)

Generated 2026-08-03. **306** tools. Verdicts: KEEP=182, STALE=19, MANUAL=4, ALREADY-ARCHIVED=58, N/A=43

Legend: `KEEP` maintained · `STALE` no commits 2y+ · `MANUAL` non-GitHub host · `ALREADY-ARCHIVED` flagged archived in code · `N/A` no project URL (system package).

> Post-fix status: the audit is now **fully clean** — the 19 STALE are marked
> `MAINTENANCE="stale"` (acknowledged legacy; modern alternatives already in the
> catalog), the 4 MANUAL are marked `MAINTENANCE="manual"` (verified by hand),
> and Stitch was re-pointed at its real GitHub repo. The single-package installer
> (`one2one --install-all`) plans **153** tools with concrete install commands;
> archived/resource/pure-reference tools are counted and skipped by design.

## Active Directory  (11)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Active Directory Tools | apt/run |
| KEEP | BloodHound (AD Attack Paths) | apt |
| KEEP | Certipy (AD Certificate Abuse) | pip |
| KEEP | Coercer (Authentication Coercion) | pip |
| KEEP | Impacket (Network Protocol Tools) | pip |
| KEEP | Kerbrute (Kerberos Brute Force) | go |
| KEEP | ldapdomaindump (AD LDAP Dumper) | pip |
| KEEP | NetExec — nxc (Network Pentesting) | pip |
| KEEP | PCredz (Credential Extractor) | git |
| KEEP | Responder (LLMNR/NBT-NS Poisoner) | git |
| KEEP | The Hacker Recipes (AD) | resource |

## Android Attack  (6)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | DroidCam (Capture Image) | git |
| ALREADY-ARCHIVED | EvilApp (Hijack Session) | git |
| ALREADY-ARCHIVED | Keydroid | git |
| ALREADY-ARCHIVED | Lockphish (Grab target LOCK PIN) | git |
| N/A | Android Hacking tools | apt/run |
| KEEP | MySMS | git |

## Anonsurf  (3)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Anonymously Hiding Tools | apt/run |
| KEEP | Anonymously Surf | git |
| KEEP | Multitor | git |

## Anonymity  (3)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | proxychains-ng (chain traffic through proxies/Tor) | apt |
| KEEP | Tor + torsocks (SOCKS anonymity proxy) | apt |
| KEEP | Whonix — Anonymity & Tor OpSec (docs) | resource |

## Cloud Security  (8)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Cloud Security Tools | apt/run |
| KEEP | Checkov (IaC Misconfig Scanner) | pip |
| KEEP | flaws.cloud (AWS Security Challenge) | resource |
| KEEP | HackTricks Cloud (cloud pentest playbook) | resource |
| KEEP | Pacu (AWS Exploitation Framework) | pip |
| KEEP | Prowler (Cloud Security Scanner) | pip |
| KEEP | ScoutSuite (Multi-Cloud Auditing) | pip |
| KEEP | Trivy (Container/K8s Scanner) | commands |

## Ddos  (7)

| Verdict | Tool | Install |
|---|---|---|
| STALE | SaphyraDDoS | git |
| ALREADY-ARCHIVED | Asyncrone | Multifunction SYN Flood DDoS Weapon | git |
| ALREADY-ARCHIVED | GoldenEye | git |
| N/A | DDOS Attack Tools | apt/run |
| N/A | SlowLoris | commands |
| KEEP | DDoS | git |
| KEEP | UFOnet | git |

## DDoS / Stress Testing  (3)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | hping3 (Packet Crafter / Flooder) | apt |
| KEEP | OWASP Denial of Service Cheat Sheet | resource |
| KEEP | slowhttptest (Slow-HTTP DoS Tester) | apt |

## Email Verifier  (2)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | Knockmail | git |
| N/A | Email Verify tools | apt/run |

## Exploit Frameworks  (8)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | WebSploit | git |
| N/A | Exploit framework | apt/run |
| KEEP | Commix | git |
| KEEP | Exploit-DB (Online Archive) | resource |
| KEEP | Metasploit Framework | apt |
| KEEP | Metasploit Unleashed (Free Course) | resource |
| KEEP | RouterSploit | git |
| KEEP | SearchSploit (Exploit-DB CLI) | apt |

## Forensics  (13)

| Verdict | Tool | Install |
|---|---|---|
| MANUAL | Disk Clone and ISO Image Acquire | commands |
| MANUAL | Toolsley | apt/run |
| N/A | Autopsy | apt/run |
| N/A | Forensic tools | apt/run |
| N/A | Wireshark | apt/run |
| KEEP | Binwalk (Firmware Analysis) | pip |
| KEEP | Bulk extractor | apt/run |
| KEEP | Eric Zimmerman's Tools | resource |
| KEEP | ExifTool (Metadata) | apt |
| KEEP | Foremost (File Carving) | apt |
| KEEP | MalwareBazaar (Sample Database) | resource |
| KEEP | pspy (Process Monitor — No Root) | commands |
| KEEP | Volatility 3 (Memory Forensics) | git |

## Hash Crack  (2)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Hash cracking tools | apt/run |
| KEEP | Hash Buster | git |

## Homograph Attacks  (2)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | EvilURL | git |
| N/A | IDN Homograph Attack | apt/run |

## Information Gathering  (27)

| Verdict | Tool | Install |
|---|---|---|
| STALE | Breacher | git |
| STALE | Port Scanner - rang3r | git |
| STALE | ReconSpider(For All Scanning) | git |
| STALE | RED HAWK (All In One Scanning) | git |
| STALE | SecretFinder (like API & etc) | git |
| ALREADY-ARCHIVED | Dracnmap | git |
| ALREADY-ARCHIVED | Find Info Using Shodan | git |
| ALREADY-ARCHIVED | Infoga - Email OSINT | git |
| ALREADY-ARCHIVED | ReconDog | git |
| ALREADY-ARCHIVED | Striker | git |
| ALREADY-ARCHIVED | Xerosploit | git |
| N/A | Host to IP  | apt/run |
| N/A | Information gathering tools | apt/run |
| N/A | IsItDown (Check Website Down/Up) | apt/run |
| N/A | Port scanning | apt/run |
| KEEP | Amass (Attack Surface Mapping) | go |
| KEEP | Gitleaks (Git Secret Scanner) | go |
| KEEP | Holehe (Email → Social Accounts) | pip |
| KEEP | httpx (HTTP Toolkit) | go |
| KEEP | Maigret (Username OSINT) | pip |
| KEEP | Masscan (Fast Port Scanner) | apt |
| KEEP | Network Map (nmap) | git |
| KEEP | RustScan (Modern Port Scanner) | commands |
| KEEP | SpiderFoot (OSINT Automation) | pip |
| KEEP | Subfinder (Subdomain Enumeration) | go |
| KEEP | theHarvester (OSINT) | git |
| KEEP | TruffleHog (Secret Scanner) | pip |

## Information gathering  (6)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | dnsx (DNS toolkit) | go |
| KEEP | EyeWitness (Web Screenshots + Headers) | git |
| KEEP | gowitness (Web Screenshots) | go |
| KEEP | naabu (fast port scanner) | go |
| KEEP | reconFTW (Automated Recon) | git |
| KEEP | Sn1per (Attack Surface Scanner) | git |

## Mix Tools  (3)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Mix tools | apt/run |
| N/A | Terminal Multiplexer | apt |
| KEEP | Crivo | git |

## Mobile Security  (7)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Mobile Security Tools | apt/run |
| KEEP | adb (Android Debug Bridge) | apt |
| KEEP | Frida (Dynamic Instrumentation) | pip |
| KEEP | Frida CodeShare | resource |
| KEEP | MobSF (Mobile Security Framework) | git |
| KEEP | Objection (Mobile Runtime Exploration) | pip |
| KEEP | OWASP MAS (Mobile App Security) | resource |

## Other Tools  (3)

| Verdict | Tool | Install |
|---|---|---|
| STALE | HatCloud(Bypass CloudFlare for IP) | git |
| N/A | Other tools | apt/run |
| KEEP | CyberChef (Cyber Swiss-Army Knife) | resource |

## Password / Hash Cracking  (7)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | CrackStation (online lookup) | resource |
| KEEP | CyberChef (the cyber swiss-army knife) | resource |
| KEEP | GTFOBins (unix binary abuse) | resource |
| KEEP | hashcat (GPU hash cracker) | apt |
| KEEP | hashes.com (hash identifier + lookup) | resource |
| KEEP | hydra (Network Login Cracker) | apt |
| KEEP | John the Ripper (jumbo) | apt |

## Payload Creation  (2)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | LOLBAS (Living Off The Land Binaries) | resource |
| KEEP | msfvenom (Payload Generator) | apt |

## Payload Creator  (9)

| Verdict | Tool | Install |
|---|---|---|
| STALE | The FatRat | git |
| STALE | Venom Shellcode Generator | git |
| MANUAL | Stitch | git |
| ALREADY-ARCHIVED | Brutal | git |
| ALREADY-ARCHIVED | Enigma | git |
| ALREADY-ARCHIVED | MSFvenom Payload Creator | git |
| ALREADY-ARCHIVED | Spycam | git |
| N/A | Payload creation tools | apt/run |
| KEEP | Mob-Droid | git |

## Payload Injection  (3)

| Verdict | Tool | Install |
|---|---|---|
| STALE | Pixload | git |
| ALREADY-ARCHIVED | Debinject | git |
| N/A | Payload Injector | apt/run |

## Phishing  (3)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | GoPhish (Phishing Simulation) | none |
| KEEP | GoPhish Documentation | resource |
| KEEP | MITRE ATT&CK — Phishing (T1566) | resource |

## Phishing Attack  (18)

| Verdict | Tool | Install |
|---|---|---|
| STALE | HiddenEye | git |
| STALE | QR Code Jacking | git |
| STALE | SayCheese | git |
| ALREADY-ARCHIVED | Autophisher RK | git |
| ALREADY-ARCHIVED | BlackEye | git |
| ALREADY-ARCHIVED | BlackPhish | git |
| ALREADY-ARCHIVED | I-See_You | git |
| ALREADY-ARCHIVED | Pyphisher | git |
| ALREADY-ARCHIVED | ShellPhish | git |
| ALREADY-ARCHIVED | Thanos | git |
| N/A | Phishing attack tools | apt/run |
| KEEP | AdvPhishing | git |
| KEEP | dnstwist | commands |
| KEEP | Evilginx3 | apt |
| KEEP | Maskphish | git |
| KEEP | QRLJacking | git |
| KEEP | Setoolkit | git |
| KEEP | SocialFish | git |

## Post Exploitation  (11)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | Chrome Keylogger | git |
| ALREADY-ARCHIVED | Havoc (C2 Framework) | git |
| ALREADY-ARCHIVED | Vegile - Ghost In The Shell | git |
| N/A | Post exploitation tools | apt/run |
| KEEP | Chisel (HTTP Tunnel) | go |
| KEEP | Evil-WinRM (Windows Remote Shell) | commands |
| KEEP | Ligolo-ng (Tunneling/Pivoting) | go |
| KEEP | Mythic (C2 Platform) | git |
| KEEP | PEASS-ng — LinPEAS/WinPEAS (Priv Esc) | commands |
| KEEP | pwncat-cs (Reverse Shell Handler) | pip |
| KEEP | Sliver (C2 Framework) | commands |

## Post exploitation  (8)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | HackTricks (post-ex / privesc playbook) | resource |
| KEEP | LaZagne (Local Credential Recovery) | git |
| KEEP | linux-smart-enumeration (lse.sh) | git |
| KEEP | LOLBAS (Windows living-off-the-land binaries) | resource |
| KEEP | mimikatz (Windows credential dumping — reference) | resource |
| KEEP | PayloadsAllTheThings (payload + technique cheatsheets) | resource |
| KEEP | pspy (unprivileged process snooping) | go |
| KEEP | revshells.com (reverse shell generator) | resource |

## Remote Administration  (6)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | Pyshell | git |
| N/A | Remote Administrator Tools (RAT) | apt/run |
| KEEP | Covenant (.NET C2) | resource |
| KEEP | hoaxshell (HTTP(S) PowerShell Reverse Shell) | git |
| KEEP | Merlin (cross-platform C2) | resource |
| KEEP | Villain (Reverse Shell / C2 Manager) | git |

## Reverse Engineering  (11)

| Verdict | Tool | Install |
|---|---|---|
| STALE | Apk2Gold | git |
| N/A | Reverse engineering tools | apt/run |
| KEEP | Androguard | commands |
| KEEP | apktool (APK Decode/Rebuild) | apt |
| KEEP | binutils (strings / objdump / readelf) | apt |
| KEEP | crackmes.one (RE Practice) | resource |
| KEEP | GDB (GNU Debugger) | apt |
| KEEP | Ghidra (NSA Reverse Engineering) | apt |
| KEEP | JadX | git |
| KEEP | Malware Unicorn RE101 (Workshop) | resource |
| KEEP | Radare2 (RE Framework) | git |

## Socialmedia  (5)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | AllinOne SocialMedia Attack | git |
| ALREADY-ARCHIVED | Application Checker | git |
| ALREADY-ARCHIVED | Facebook Attack | git |
| ALREADY-ARCHIVED | Instagram Attack | commands |
| N/A | SocialMedia Bruteforce | apt/run |

## Socialmedia Finder  (5)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | Find SocialMedia By Facial Recognation System | git |
| ALREADY-ARCHIVED | Find SocialMedia By UserName | git |
| N/A | SocialMedia Finder | apt/run |
| KEEP | Sherlock | git |
| KEEP | SocialScan | Username or Email | pip |

## Sql Injection  (8)

| Verdict | Tool | Install |
|---|---|---|
| STALE | SQLScan | commands |
| ALREADY-ARCHIVED | Blisqy - Exploit Time-based blind-SQL injection | git |
| ALREADY-ARCHIVED | Explo | git |
| ALREADY-ARCHIVED | Leviathan - Wide Range Mass Audit Toolkit | git |
| N/A | SQL Injection Tools | apt/run |
| KEEP | Damn Small SQLi Scanner | git |
| KEEP | NoSqlMap | git |
| KEEP | Sqlmap tool | git |

## SQL Injection  (3)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | Ghauri (Modern SQLi Tool) | pip |
| KEEP | PayloadsAllTheThings — SQL Injection | resource |
| KEEP | PortSwigger — SQL Injection Labs | resource |

## Steganography  (13)

| Verdict | Tool | Install |
|---|---|---|
| STALE | Stegseek (fast steganography cracker) | apt |
| ALREADY-ARCHIVED | StegoCracker | git |
| ALREADY-ARCHIVED | Whitespace | git |
| N/A | Steganography Tools | apt/run |
| N/A | SteganoHide | apt |
| KEEP | Aperi'Solve (all-in-one image stego) | resource |
| KEEP | ExifTool (metadata reader) | apt |
| KEEP | Futureboy Stegano decoder | resource |
| KEEP | outguess (JPEG stego) | apt |
| KEEP | stego-toolkit (Docker kit + checklist) | resource |
| KEEP | StegOnline (in-browser LSB explorer) | resource |
| KEEP | stegseek (fast steghide cracker) | git |
| KEEP | zsteg (PNG/BMP LSB detector) | commands |

## Tool Manager  (3)

| Verdict | Tool | Install |
|---|---|---|
| N/A | Uninstall One2One | apt/run |
| N/A | Update or Uninstall | One2One | apt/run |
| N/A | Update Tool or System | apt/run |

## Web Attack  (27)

| Verdict | Tool | Install |
|---|---|---|
| STALE | SubDomain Finder | git |
| MANUAL | Dirb | git |
| ALREADY-ARCHIVED | Blazy(Also Find ClickJacking) | commands |
| ALREADY-ARCHIVED | CheckURL | git |
| ALREADY-ARCHIVED | Web2Attack | git |
| N/A | Skipfish | apt/run |
| N/A | Web Attack tools | apt/run |
| KEEP | Arjun (HTTP Parameter Discovery) | pip |
| KEEP | Caido (Web Security Auditing) | commands |
| KEEP | Dirsearch (Web Path Discovery) | pip |
| KEEP | Feroxbuster (Directory Brute Force) | apt |
| KEEP | ffuf (Web Fuzzer) | go |
| KEEP | Gobuster (Dir/DNS/Vhost Brute Force) | go |
| KEEP | HackTricks | resource |
| KEEP | Katana (Web Crawler) | go |
| KEEP | mitmproxy (Intercepting Proxy) | pip |
| KEEP | Nikto (Web Server Scanner) | apt |
| KEEP | Nuclei (Vulnerability Scanner) | go |
| KEEP | OWASP ZAP (Web App Scanner) | apt |
| KEEP | PayloadsAllTheThings | resource |
| KEEP | PortSwigger Web Security Academy | resource |
| KEEP | revshells.com (Reverse Shell Generator) | resource |
| KEEP | Sub-Domain TakeOver | git |
| KEEP | testssl.sh (TLS/SSL Checker) | git |
| KEEP | wafw00f (WAF Detector) | git |
| KEEP | WhatWeb (Web Fingerprinter) | apt |
| KEEP | WPScan (WordPress Scanner) | apt |

## Web Crawling  (2)

| Verdict | Tool | Install |
|---|---|---|
| STALE | Gospider | commands |
| N/A | Web crawling | apt/run |

## Wifi Jamming  (3)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | KawaiiDeauther | git |
| ALREADY-ARCHIVED | WifiJammer-NG | git |
| N/A | Wifi Deauthenticate | apt/run |

## Wireless Attack  (14)

| Verdict | Tool | Install |
|---|---|---|
| STALE | WiFi-Pumpkin | git |
| ALREADY-ARCHIVED | EvilTwin | git |
| ALREADY-ARCHIVED | Fastssh | git |
| N/A | Howmanypeople | apt |
| N/A | Wireless attack tools | apt/run |
| KEEP | Airgeddon (Wireless Attack Suite) | git |
| KEEP | Bettercap (Network/WiFi/BLE MITM) | apt |
| KEEP | Bluetooth Honeypot GUI Framework | commands |
| KEEP | Fluxion | git |
| KEEP | hcxdumptool (PMKID Capture) | git |
| KEEP | hcxtools (PMKID/Hash Conversion) | git |
| KEEP | pixiewps | git |
| KEEP | Wifiphisher | git |
| KEEP | Wifite | git |

## Wireless attack  (6)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | aircrack-ng (WiFi security suite) | apt |
| KEEP | Aircrack-ng: cracking WPA (tutorial) | resource |
| KEEP | hashcat example hashes (WPA mode 22000) | resource |
| KEEP | Kismet (wireless detector / WIDS) | apt |
| KEEP | Reaver (WPS PIN attack) | apt |
| KEEP | WiGLE (wardriving map & API) | resource |

## Wordlist Generation  (4)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | CeWL (Custom Word List) | apt |
| KEEP | crunch (Wordlist Generator) | apt |
| KEEP | Kali wordlists package (rockyou etc.) | resource |
| KEEP | SecLists (Wordlist Collection) | resource |

## Wordlist Generator  (8)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | Goblin WordGenerator | git |
| ALREADY-ARCHIVED | Password list (1.4 Billion Clear Text Password) | git |
| ALREADY-ARCHIVED | WordlistCreator | git |
| N/A | Wordlist Generator | apt/run |
| KEEP | Cupp | git |
| KEEP | haiti (Hash Type Identifier) | commands |
| KEEP | Hashcat (Password Cracker) | apt |
| KEEP | John the Ripper | apt |

## XSS  (3)

| Verdict | Tool | Install |
|---|---|---|
| KEEP | kxss (Reflection Finder) | go |
| KEEP | PayloadsAllTheThings — XSS Injection | resource |
| KEEP | PortSwigger — XSS Labs | resource |

## Xss Attack  (10)

| Verdict | Tool | Install |
|---|---|---|
| ALREADY-ARCHIVED | Extended XSS Searcher and Finder | git |
| ALREADY-ARCHIVED | RVuln | git |
| ALREADY-ARCHIVED | XanXSS | git |
| ALREADY-ARCHIVED | XSpear | commands |
| ALREADY-ARCHIVED | XSS-Freak | git |
| ALREADY-ARCHIVED | XSSCon | git |
| N/A | XSS Attack Tools | apt/run |
| KEEP | Advanced XSS Detection Suite | git |
| KEEP | DalFox (Finder of XSS) | apt |
| KEEP | XSS Payload Generator | git |
