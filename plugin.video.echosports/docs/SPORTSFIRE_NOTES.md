# Sportsfire Reverse Engineering Notes

**Status:** BLOCKED - Decryption not working  
**Last updated:** March 2026  
**APK analyzed:** `Sportsfire_AF_2_0_8_Custom_Arm7_Mu1tiPa1ch_Spydog_TvDevicesOnly.apk`

---

## IMPORTANT: NOT Same As LeagueDo

We successfully cracked wilderness.click (LeagueDo's embed player) using a custom base64 chunk-reorder algorithm. **Sportsfire uses a COMPLETELY DIFFERENT encryption scheme.**

| Property | LeagueDo/wilderness.click | Sportsfire |
|----------|---------------------------|------------|
| Input format | Base64 string | Hex string (0-9a-f only) |
| Algorithm | Custom base64 chunk reorder | Standard DES (confirmed from native lib) |
| Key visible? | No key (algorithm only) | Key found: `ww23qq8811hh22aa` |
| Decryption working? | ✅ YES | ❌ NO |

---

## Files Location

```
/home/claude/sportsfire_arm7/                    # Extracted APK
/home/claude/sportsfire_arm7/lib/armeabi-v7a/libcompression.so   # Native crypto library (25KB)
/home/claude/sportsfire_arm7/decompiled/         # JADX decompiled Java source
/home/claude/sportsfire_arm7/classes*.dex        # Original DEX files
```

## Tools Installed

- `jadx` at `/tmp/jadx/bin/jadx` (v1.5.0)
- `pycryptodome` (pip3) - for DES/3DES
- `capstone` (pip3) - ARM disassembler

---

## API Details

### Schedule API (WORKING)
```
POST https://spfire.work/tv/index.php?case=get_schedule_by_type
Headers:
  Content-Type: application/x-www-form-urlencoded
  app-token: 9120163167c05aed85f30bf88495bd89
  User-Agent: USER-AGENT-tvtap-APP-V2
Body:
  type=0   (0=all, 5=NHL, 7=NBA, etc.)

Response: JSON with schedulers[].channels[].http_stream (ENCRYPTED)
```

### Stream Link API (NEEDS AUTH)
```
POST https://spfire.work/tv/index.php?case=get_valid_link_revision
Headers: (same as above)
Body:
  username=<CRC value from session>
  channel_id=<pk_id>
  type=<cat_id>
  mainP=<payload from Utils.getPayload()>

Response: JSON with msg.channel[0].http_stream (ENCRYPTED)
```

---

## Crypto Analysis - CONFIRMED FINDINGS

### Algorithm: Standard DES
All lookup tables in libcompression.so verified to match textbook DES exactly:
- IP, IP⁻¹ (Initial/Inverse Permutation) ✓
- PC-1, PC-2 (Key schedule permutations) ✓
- S-boxes (all 8) ✓
- E (Expansion permutation) ✓
- P (P-box) ✓
- shiftBits ✓

**Tables stored as 32-bit little-endian integers at these offsets:**
```
.data section base: 0x6000 (file offset)
VA-to-file: VA - 0x2000

IP table:      VA 0x6010, file 0x4010
FP table:      VA 0x6110, file 0x4110  
E table:       VA 0x6210, file 0x4210
P table:       VA 0x6290, file 0x4290
PC1 table:     VA 0x6310, file 0x4310
PC2 table:     VA 0x6420, file 0x4420
shiftBits:     VA 0x64c0, file 0x44c0
S-boxes:       VA 0x6500, file 0x4500 (8 boxes × 64 entries × 4 bytes = 2048 bytes)
```

### Key
```
String key = "ww23qq8811hh22aa";   // 16 bytes, defined in VideoPlayerActivity.java line 69
```

### Native Functions (libcompression.so)
```
Export                                              Address
─────────────────────────────────────────────────────────────
Java_com_leed_sportsfire_ui_VideoPlayerActivity_Crypt    0x23f5
Java_com_leed_sportsfire_ui_ExoPlayerHTTPActivity_Crypt  0x2821
_edCryption                                              0x44d5
arrayCryption                                            0x4541
LoopF (Feistel function)                                 0x4635
initKey                                                  0x42f1
leftMoveKey                                              0x43a1
make_SubKey                                              0x4411
checksign                                                0x2445
_AllOK                                                   0x2259
```

### Java Decryption Flow (VideoPlayerActivity.java)
```java
// Line 190-192
private String parse_url(String enc) {
    return new String(Crypt(Base64.decode(enc, 0), this.key.getBytes(), 0, "nothing", "nothing", 0));
}

// Line 356 - native method declaration
public native byte[] Crypt(byte[] bArr, byte[] bArr2, int i, String str, String str2, int i2);
```

**Flow:** `http_stream` → `Base64.decode()` → `Crypt()` native → `new String()` → URL

---

## The Problem

### What API Returns
```
http_stream: "72f978e29d53c6ec18bf6337fd0d40108126652ef34c685e4b0f4f34fef97664..."
```
- All characters are 0-9, a-f (looks like HEX)
- Length 80-400+ chars
- Valid as both HEX (→ 40 bytes) and Base64 (→ 60 bytes)

### What We Tried (ALL FAILED)
| Interpretation | Key | Mode | Result |
|----------------|-----|------|--------|
| Base64 decode | key[:8] `ww23qq88` | DES-ECB | Garbage |
| Base64 decode | key[8:] `11hh22aa` | DES-ECB | Garbage |
| Base64 decode | key[:8] | DES-CBC iv=`nothing\0` | Garbage |
| Base64 decode | full 16-byte | 3DES-ECB | Garbage |
| Hex decode | key[:8] | DES-ECB | Garbage |
| Hex decode | key[:8] | DES-ECB encrypt | Garbage |
| Base64 decode | XOR(key[:8], key[8:]) | DES-ECB | Garbage |
| Base64 decode | MD5(key)[:8] | DES-ECB | Garbage |
| Base64 decode | reversed key | DES-ECB | Garbage |

### Hypotheses Not Yet Tested
1. **Modified APK** - This is "Mu1tiPa1ch_Spydog" version; crypto may be patched
2. **Auth-dependent format** - Authenticated API requests may return different data format
3. **Server transformation** - Data may be XOR'd or transformed before DES encryption
4. **Encrypt vs Decrypt direction** - Native code may use "encrypt" to decode (reversed subkeys)
5. **Key derivation** - Key may be hashed/transformed before use in ways not visible in Java

---

## Recommended Next Steps

### Option A: Traffic Capture (RECOMMENDED)
Run actual Sportsfire app with mitmproxy/Charles Proxy to capture:
1. Exact HTTP request/response for `get_valid_link_revision`
2. Whether authenticated requests return different format
3. What format the app actually receives vs what we're getting

### Option B: Find Original APK
Look for unmodified Sportsfire APK to verify if this patched version changed the crypto.

### Option C: Dynamic Analysis
Use Frida to hook the native `Crypt` function and log actual input/output at runtime.

---

## Test Data Samples

### Encrypted stream (from schedule API, March 2026)
```
Event: Rangers vs Panthers
Channel: MSG
http_stream: 72f978e29d53c6ec18bf6337fd0d40108126652ef34c685e4b0f4f34fef97664ada003b97cdf31d34ff5e11bf81f52ee1e9f7f7f7efa3b5e9eb9fb5edfb77e7cbd7fbc7d5b5ddd7fb5b7b1f3edcfddf77fe767b7b8f97376bfce1df67e79e7fbdfbf6fbfef7e7d57bffbbffef7dff7fb3f3efdbf87f3f73

Base64 decoded (60 bytes): ef67fdefc7b6f5de7773a79cd7c6dfeb7dfb7ddd1de34d74f35dbaeb9d9e7f7e...
Hex decoded (40 bytes): 72f978e29d53c6ec18bf6337fd0d4010...
```

---

## Code References

### VideoPlayerActivity.java key sections
- Line 69: Key definition
- Line 177: API call to `get_valid_link_revision`
- Line 190-192: `parse_url()` decryption
- Line 356: Native method declaration
- Line 389-392: Stream URL extraction from API response

### Security.java
- `convertHexToString()` - converts hex to ASCII string
- `getMyBigString()` / `getMySmallString()` - native methods for RSA keys

---

## Session Commands for Quick Resume

```bash
# Decompile again if needed
/tmp/jadx/bin/jadx -d /home/claude/sportsfire_arm7/decompiled --no-res /home/claude/sportsfire_arm7/classes*.dex

# View VideoPlayerActivity
cat /home/claude/sportsfire_arm7/decompiled/sources/com/leed/sportsfire/ui/VideoPlayerActivity.java

# Disassemble native function
python3 -c "
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
with open('/home/claude/sportsfire_arm7/lib/armeabi-v7a/libcompression.so', 'rb') as f:
    f.seek(0x44d4)  # _edCryption
    code = f.read(300)
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
for insn in md.disasm(code, 0x44d4):
    print(f'0x{insn.address:04x}: {insn.mnemonic:8} {insn.op_str}')
"

# Test API
curl -X POST "https://spfire.work/tv/index.php?case=get_schedule_by_type" \
  -H "app-token: 9120163167c05aed85f30bf88495bd89" \
  -H "User-Agent: USER-AGENT-tvtap-APP-V2" \
  -d "type=0"
```
