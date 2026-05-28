import matplotlib.pyplot as plt

# 设置字体为 Times New Roman
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman']

# 1. 准备数据 (基于你的 LaTeX 代码)
labels = [
    'Recovery &\nExecution',
    'Persistence &\nMonotonicity',
    'Dependency &\nTopology',
    'Message Binding\n& Signature',
    'Resource &\nOperational Visibility'
]
# 具体的 bug 数量
bug_counts = [4, 4, 3, 2, 2]
total_bugs = sum(bug_counts)

# 2. 设置莫兰迪色系 (低饱和度学术风)
colors = ['#8ECFC9', '#FFBE7A', '#FA7F6F', '#82B0D2', '#BEB8DC']

# 3. 创建画布 (加大画布尺寸)
fig, ax = plt.subplots(figsize=(20, 20), dpi=100)

# 4. 自定义显示函数：百分比和数量分两行显示
def make_autopct(counts):
    def autopct(pct):
        count = int(round(pct * total_bugs / 100.0))
        return f'{pct:.1f}%\n{count}'
    return autopct

# 5. 绘制环形图
# 环形宽度设为0.7，内半径=0.3，外半径=1，中心位置=(0.3+1)/2=0.65
wedges, texts, autotexts = ax.pie(
    bug_counts, 
    labels=labels, 
    autopct=make_autopct(bug_counts), 
    startangle=140, 
    colors=colors,
    radius=1.2,          # 饼图半径更大
    pctdistance=0.65,    # 百分比居中在环形区域
    labeldistance=1.18,  # 标签距离中心的距离（越大越远离圆心）
    wedgeprops={'width': 0.7, 'edgecolor': 'white', 'linewidth': 3},
    textprops={'fontsize': 56, 'family': 'serif', 'weight': 'normal'}
)

# 6. 美化百分比数字 - 加粗加大
plt.setp(autotexts, size=58, weight="normal", color="white")

# 调整布局防止标签重叠
plt.tight_layout()

# 保存为图片
plt.savefig('bug_class_distribution.png', bbox_inches='tight', pad_inches=0.8, dpi=300)
print("图片已保存: bug_class_distribution.png")