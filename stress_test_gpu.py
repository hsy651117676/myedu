"""
Tesla P4 压力测试 - 修正版
单引擎实例，串行处理模拟真实负载
"""

import os
import time
import subprocess
import threading
from datetime import datetime
from PIL import Image
import numpy as np

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# ==================== 配置 ====================
TEST_DURATION = 600  # 10分钟
LOG_FILE = "/tmp/p4_stress_test.log"
# =============================================

stop_flag = threading.Event()
monitor_data = []


def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_gpu_stats():
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,clocks.sm,clocks.mem,pstate",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        parts = result.stdout.strip().split(", ")
        return {
            "gpu_util": parts[1],
            "mem_used": parts[2],
            "mem_total": parts[3],
            "temp": parts[4],
            "power": parts[5].replace("W", "").strip(),
            "sm_clock": parts[6],
            "pstate": parts[7],
        }
    except Exception as e:
        return None


def monitor_worker():
    """每秒记录 GPU 状态"""
    log("📊 监控线程启动")
    while not stop_flag.is_set():
        stats = get_gpu_stats()
        if stats:
            monitor_data.append(
                {
                    "timestamp": datetime.now(),
                    "gpu_util": int(stats["gpu_util"]),
                    "mem_used": int(stats["mem_used"]),
                    "temp": int(stats["temp"]),
                    "power": float(stats["power"] or 0),
                    "sm_clock": int(stats["sm_clock"]),
                    "pstate": stats["pstate"],
                }
            )

            temp = int(stats["temp"])
            mem_used = int(stats["mem_used"])

            if temp >= 80:
                log(f"⚠️  温度告警: {temp}°C")
            elif temp >= 85:
                log(f"🔥 危险温度: {temp}°C，即将降频！")

            if stats["pstate"] not in ("P8", "P0") and stats["pstate"] != "P0":
                log(f"⚡ 降频: P-State={stats['pstate']}, 时钟={stats['sm_clock']}MHz")

        time.sleep(1)
    log("📊 监控线程结束")


def create_test_images(count=30):
    """创建测试图片，模拟真实扫描件"""
    log(f"📝 生成 {count} 张测试图片（模拟 A4 扫描件）...")
    images = []
    for i in range(count):
        # 模拟 300DPI A4 扫描件：2480×3508，缩放到一半保证速度
        w, h = 1240, 1754
        img = Image.new("RGB", (w, h), color=(252, 250, 242))

        # 随机噪点模拟扫描效果
        arr = np.array(img)
        noise = np.random.randint(0, 12, arr.shape, dtype=np.uint8)
        arr = np.clip(arr - noise, 0, 255)
        img = Image.fromarray(arr)

        images.append(img)

    log(f"✅ 测试图片生成完成（{count}张，{w}×{h}）")
    return images


def ocr_stress_worker(engine, images):
    """单引擎串行处理，模拟持续负载"""
    total = 0
    errors = 0
    times = []

    log("🚀 开始 OCR 压力测试...")
    log(f"   图片数量: {len(images)} 张，循环处理 {TEST_DURATION} 秒\n")

    start_time = time.time()
    last_report = start_time

    while not stop_flag.is_set():
        for img in images:
            if stop_flag.is_set():
                break

            try:
                t0 = time.time()
                result, _ = engine(img)
                elapsed = time.time() - t0

                times.append(elapsed)
                total += 1

                # 每秒最多处理大约 8 张（0.12s/张），不需要额外 sleep
                # 但如果太快可以加一点间隔模拟真实场景
                # time.sleep(0.05)

            except Exception as e:
                errors += 1
                log(f"❌ 处理失败 ({errors}): {str(e)[:200]}")
                if "out of memory" in str(e).lower():
                    log(f"💥 显存不足，停止测试")
                    stop_flag.set()
                    break
                time.sleep(1)

            # 每 5 秒报告一次
            now = time.time()
            if now - last_report >= 5:
                stats = get_gpu_stats()
                if stats:
                    avg_time = sum(times[-100:]) / min(len(times), 100) if times else 0
                    qps = 1 / avg_time if avg_time > 0 else 0
                    log(
                        f"📊 已处理: {total}张 | "
                        f"速度: {qps:.1f}张/s | "
                        f"平均耗时: {avg_time * 1000:.1f}ms | "
                        f"温度: {stats['temp']}°C | "
                        f"功耗: {stats['power']}W | "
                        f"利用率: {stats['gpu_util']}% | "
                        f"显存: {stats['mem_used']}MB"
                    )
                last_report = now

    end_time = time.time()
    duration = end_time - start_time

    log(f"\n✅ OCR 测试结束")
    log(f"   总处理: {total} 张")
    log(f"   总耗时: {duration:.1f} 秒")
    log(f"   平均速度: {total / duration:.1f} 张/秒")
    log(f"   错误数: {errors}")
    if times:
        log(f"   最快: {min(times) * 1000:.1f}ms")
        log(f"   最慢: {max(times) * 1000:.1f}ms")
        log(f"   平均: {sum(times) / len(times) * 1000:.1f}ms")


def print_summary():
    """打印完整测试总结"""
    log("\n" + "=" * 60)
    log("📊 压力测试总结")
    log("=" * 60)

    if not monitor_data:
        log("无监控数据")
        return

    temps = [d["temp"] for d in monitor_data]
    powers = [d["power"] for d in monitor_data]
    utils = [d["gpu_util"] for d in monitor_data]
    mems = [d["mem_used"] for d in monitor_data]
    pstates = [d["pstate"] for d in monitor_data]

    log(f"\n测试时长: {len(monitor_data)} 秒")
    log(f"GPU 温度:")
    log(f"  - 最低: {min(temps)}°C")
    log(f"  - 最高: {max(temps)}°C")
    log(f"  - 平均: {sum(temps) / len(temps):.1f}°C")
    log(f"GPU 功耗:")
    log(f"  - 最低: {min(powers):.1f}W")
    log(f"  - 最高: {max(powers):.1f}W")
    log(f"  - 平均: {sum(powers) / len(powers):.1f}W")
    log(f"GPU 利用率 - 最高: {max(utils)}%")
    log(f"显存 - 最大使用: {max(mems)}MB")

    # 温度分布
    log(f"\n温度分布:")
    ranges = [
        ("30-40°C", 30, 40),
        ("40-50°C", 40, 50),
        ("50-60°C", 50, 60),
        ("60-70°C", 60, 70),
        ("70-80°C", 70, 80),
        ("80-85°C", 80, 85),
        (">85°C", 85, 999),
    ]
    for label, lo, hi in ranges:
        count = sum(1 for t in temps if lo <= t < hi)
        if count > 0:
            pct = count / len(temps) * 100
            bar = "█" * int(pct / 2)
            log(f"  {label:>10}: {count:4d}秒 ({pct:5.1f}%) {bar}")

    # 降频检测
    unique_pstates = set(pstates)
    log(f"\nP-State 分布: {unique_pstates}")
    if "P0" in unique_pstates and len(unique_pstates) <= 2:
        log("✅ 未检测到降频，GPU 全程满速运行")
    elif len(unique_pstates) > 2:
        log(f"⚠️  检测到 P-State 切换，可能发生降频")
    else:
        log(f"⚠️  GPU 未进入 P0 满速状态")

    # 最终判断
    max_temp = max(temps)
    log(f"\n{'=' * 40}")
    if max_temp < 65:
        log(f"✅ 结论：P4 散热优秀，最高 {max_temp}°C，完全不用担心过热")
    elif max_temp < 75:
        log(f"🟡 结论：P4 温度可接受，最高 {max_temp}°C，长时间运行没问题")
    elif max_temp < 85:
        log(f"🟠 结论：P4 温度偏高，最高 {max_temp}°C，建议检查机箱风道")
    else:
        log(f"🔴 结论：P4 过热！最高 {max_temp}°C，必须加强散热")


def main():
    log("=" * 60)
    log("🔥 Tesla P4 压力测试（单引擎模式）")
    log("=" * 60)
    log(f"测试时长: {TEST_DURATION}s ({TEST_DURATION // 60}分钟)")
    log(f"模式: 单引擎 + 持续推理")
    log(f"")

    # 初始状态
    stats = get_gpu_stats()
    if stats:
        log(
            f"初始状态: 温度={stats['temp']}°C, 功耗={stats['power']}W, 显存={stats['mem_used']}MB"
        )
    else:
        log("❌ 无法检测到 GPU，退出")
        return

    # 创建测试图片
    images = create_test_images(30)

    # 初始化 OCR 引擎（只加载一次）
    log("\n🔧 初始化 OCR 引擎（首次加载约8秒）...")
    from rapidocr_onnxruntime import RapidOCR

    t0 = time.time()
    engine = RapidOCR(
        det_use_cuda=True,
        cls_use_cuda=True,
        rec_use_cuda=True,
    )
    log(f"✅ 引擎初始化完成，耗时 {time.time() - t0:.1f}s")

    # 查看加载后显存
    stats = get_gpu_stats()
    if stats:
        log(f"加载后显存: {stats['mem_used']}MB\n")

    # 启动监控
    monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
    monitor_thread.start()

    # 启动 OCR 工作线程（只有一个）
    worker = threading.Thread(target=ocr_stress_worker, args=(engine, images))
    worker.start()

    # 等待测试时长
    time.sleep(TEST_DURATION)
    stop_flag.set()

    worker.join(timeout=30)
    monitor_thread.join(timeout=5)

    print_summary()
    log(f"\n📄 完整日志: {LOG_FILE}")


if __name__ == "__main__":
    main()
