import numpy as np
import matplotlib.pyplot as plt



# &ISIC  &68.75/68.57 &68.73/68.56 &71.44/71.40\\ 
# &SOPHIE&82.44/82.41 &83.10/83.03 &85.20/84.99\\ 
# &PUMA  &65.32/65.20 &67.86/67.71 &70.15/69.99\\ 
# 设置数据
sensors = [10, 20, 50, 100]
ISIC = {
    'ISIC': [69.12, 68.80, 67.95 ,67.11],
}

SOPHIE = {
    'SOPHIE': [82.75, 82.63,81.74,80.04], 
}
PUMA = {
    'PUMA':[66.13, 65.77,64.25,63.91],

}

sensors = [2, 3, 5, 8]
ISIC = {
    'ISIC': [69.02,69.07,69.12,69.19 ],
}

SOPHIE = {
    'SOPHIE': [82.58,82.70,82.75,82.91 ], 
}
PUMA = {
    'PUMA':[65.93,66.07,66.13,66.28 ],

}



cmap = plt.get_cmap('tab20c')
cmap = plt.get_cmap('Set1')
colors = [cmap(1),cmap(2), cmap(3), cmap(4),cmap(6),cmap(7)]

# 绘制图像
fig, axs = plt.subplots(1, 3, figsize=(15, 5))


def plot_bars(ax, data, ylabel, title):
    width = 0.4
    x = np.arange(len(sensors))

    for label, values in data.items():
        # 柱状图
        bars = ax.bar(
            x, values, width,
            label=label,
            color=colors[0],
            edgecolor='white',
            hatch='///'
        )

        # 折线图（柱子中点）
        ax.plot(x, values, marker='s', linestyle='-', color='gray', linewidth=2, markersize=10)

    ax.set_xticks(x)
    ax.set_xticklabels(sensors, fontsize=22)
    ax.set_ylabel(ylabel, fontdict={'size': 24})
    ax.set_xlabel('noise scale', fontdict={'size': 24})
    ax.set_title(title, fontdict={'size': 24})
    ax.tick_params(axis='y', labelsize=18) 

# 子图 (a) Accuracy
plot_bars(axs[0], ISIC, 'Accuracy (%)', '(a) ISIC')
axs[0].set_ylim(20, 90) 

# 子图 (b) Latency
plot_bars(axs[1], SOPHIE, 'Accuracy (%)', '(b) SOPHIE')
axs[1].set_ylim(20, 95) 

# 子图 (c) total_memory
plot_bars(axs[2], PUMA, 'Accuracy (%)', '(c) PUMA')
axs[2].set_ylim(20, 95)

plt.tight_layout(rect=[0, 0, 1, 0.9])  
plt.show()
