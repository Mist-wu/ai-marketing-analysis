AI与市场营销 平时作业：复现一项课内任务
薛熙辰 | 2026-10-28
复现内容：客户资产管理实训，任务一，指令1-1。
在线报告：https://x6c.pages.dev/

打开“薛熙辰_订单数据探索性分析.html”即可离线阅读交互式报告。
figures/ 内含五张1980×1080 PNG；results/ 内含汇总CSV和计算结果。

实际使用：Codex（ChatGPT）辅助编写和执行 Python / pandas 分析；网页用 React 图表展示，PNG用matplotlib生成。
输入：从课程主页下载的orders.xlsx，工作表orders，87,801条订单、15,000位客户。
观察期：2023-01-01 至 2024-12-30。
源文件SHA-256：749ed60a60c64e2826b5d75554a2ed8f3a5897fe79e9a03c76ed69b63dd98f63
原始课程文件请从云邮课程主页获取。本成果包仅包含汇总结果，没有逐单或逐客户明细。

重算方法（Python 3.10+）：
1. 安装 pandas numpy openpyxl matplotlib。
2. python analyze_orders.py /实际路径/orders.xlsx
3. python render_figures.py
重新运行会更新本目录results/中的汇总结果。网页为已核验的成果快照，不会因重算自动改变。
PNG中文字体优先使用macOS黑体；其他系统需配置可用的中文字体。

已完成核验：主键重复、整行重复、缺失字段、非正金额、非法数量、未识别品类均为0；
各分布订单数汇总均为87,801；频次数量合计15,000位客户，加权订单数87,801；
用Counter复核品类与客户频次，用Decimal复核金额总和24,433,149.59元。
时间补零仅代表文件中无订单记录，不等于已证实真实零交易。
