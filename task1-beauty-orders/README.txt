AI 与市场营销 平时作业：复现一项课内任务
薛熙辰 | 2026-10-28
复现内容：客户资产管理实训，任务一，指令 1-1。
本任务的报告是同目录的“薛熙辰_订单数据探索性分析.html”，用浏览器离线打开。
第二题的在线报告在 https://x6c.pages.dev/ 。
figures/ 内含五张 1980×1080 PNG；results/ 内含汇总 CSV 和计算结果。

实际使用：Codex（ChatGPT）辅助编写和执行 Python / pandas 分析；网页用 React 图表展示，PNG 用 matplotlib 生成。
输入：从课程主页下载的 orders.xlsx，工作表 orders，87,801 条订单、15,000 位客户。
观察期：2023-01-01 至 2024-12-30。
源文件 SHA-256:749ed60a60c64e2826b5d75554a2ed8f3a5897fe79e9a03c76ed69b63dd98f63
原始课程文件请从云邮课程主页获取。本成果包仅包含汇总结果，没有逐单或逐客户明细。

重算方法（Python 3.10+）：
1. 安装 pandas numpy openpyxl matplotlib。
2. python analyze_orders.py /实际路径/orders.xlsx
3. python render_figures.py
分析脚本更新 results/，同时导出 reviewed.json，供原作业的 finalize_report.py 补全元数据后写入 report-app/src/data.json。
本目录的离线 HTML 是已核验的独立快照，重算只更新数据和 PNG。
PNG 中文字体优先使用 macOS 黑体；其他系统需配置可用的中文字体。

已完成核验：主键重复、整行重复、缺失字段、非正金额、非法数量、未识别品类均为 0；
各分布订单数汇总均为 87,801；频次数量合计 15,000 位客户，加权订单数 87,801；
用 Counter 复核品类与客户频次，用 Decimal 复核金额总和 24,433,149.59 元。
时间补零仅代表文件中无订单记录，不等于已证实真实零交易。
