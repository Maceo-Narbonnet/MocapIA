import numpy as np
from scipy.optimize import least_squares

def project_point(P: np.ndarray, X: np.ndarray) -> np.ndarray:
    """
    用投影矩阵P将3D点X投影到2D平面。
    Args:
        P: 投影矩阵 (3, 4)
        X: 3D点 (3,) 或 (3, 1)
    Returns:
        2D点 (2,)
    """
    X_h = np.append(X, 1)  # 转为齐次坐标
    proj = P @ X_h
    return proj[:2] / proj[2]

def reprojection_error_func(X, P_list, pts_2d_list):
    """
    计算当前3D点X的重投影误差。
    Args:
        X: 当前3D点 (3,)
        P_list: 投影矩阵列表，每个shape为(3,4)
        pts_2d_list: 观测到的2D点列表，每个shape为(2,)
    Returns:
        所有相机的重投影误差拼接成的1D数组
    """
    error = []
    for P, pts_2d in zip(P_list, pts_2d_list):
        proj_2d = project_point(P, X)
        error.extend(proj_2d - pts_2d)
    return np.array(error)

def optimize_3d_point(P_list, pts_2d_list, X_init):
    """
    对单个3D点进行重投影优化。
    Args:
        P_list: 投影矩阵列表
        pts_2d_list: 2D点列表
        X_init: 初始3D点 (3,)
    Returns:
        优化后的3D点 (3,)
    """
    result = least_squares(
        reprojection_error_func, X_init, args=(P_list, pts_2d_list), method='lm'
    )
    return result.x

# 示例用法
if __name__ == "__main__":
    # 假设有两个相机
    P1 = np.random.rand(3, 4)
    P2 = np.random.rand(3, 4)
    pts_2d_list = [np.array([100, 200]), np.array([120, 210])]
    X_init = np.array([10, 20, 30])
    X_opt = optimize_3d_point([P1, P2], pts_2d_list, X_init)
    print("优化后的3D点：", X_opt)