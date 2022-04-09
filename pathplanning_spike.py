#!/usr/bin/env python3
import time
from dataclasses import dataclass

import networkx as nx
import numpy as np
import pylab as pl
from nicegui import ui
from scipy import spatial

from rosys.actors.pathplanning import PlannerProcess
from rosys.actors.pathplanning import plot_tools as pt
from rosys.actors.pathplanning.robot_renderer import RobotRenderer
from rosys.helpers import angle
from rosys.world import Area, Obstacle, PathSegment, Point, Pose, Spline

robot_outline = [(-0.5, -0.5), (0.5, -0.5), (0.75, 0), (0.5, 0.5), (-0.5, 0.5)]
areas = [Area(id='main', outline=[Point(x=-5, y=-5), Point(x=25, y=-5), Point(x=25, y=25), Point(x=-5, y=25)])]
obstacles = [Obstacle(id='0', outline=[Point(x=5, y=-5), Point(x=15, y=-5), Point(x=15, y=15), Point(x=5, y=15)])]
start = Pose()
goal = Pose(x=20, y=0, yaw=0)
planner = PlannerProcess(None, robot_outline)
plot = ui.plot(figsize=(14, 8))


def run_old():
    t = time.time()
    planner.update_obstacle_map(areas, obstacles, [start, goal], deadline=time.time()+10.0)
    planner.update_distance_map(goal, deadline=time.time()+10.0)
    dt0 = time.time() - t
    t = time.time()
    path = planner.search(goal=goal, start=start, backward=False, deadline=time.time()+10.0)
    dt1 = time.time() - t

    with plot:
        pl.clf()
        pl.title(f'{dt0:.3f} s + {dt1:.3f} s')
        pt.show_distance_map(planner.state.distance_map)
        pt.show_obstacle_map(planner.state.obstacle_map)
        pl.gca().invert_yaxis()
        pl.autoscale(False)
        pt.plot_path(path, 'C0')
        robot_renderer = RobotRenderer(robot_outline)
        pt.plot_robot(robot_renderer, (start.x, start.y, start.yaw), 'C2', lw=1)
        for step in path:
            yaw = step.spline.yaw(1) + np.pi if step.backward else step.spline.yaw(1)
            pt.plot_robot(robot_renderer, (step.spline.x(1), step.spline.y(1), yaw), 'C2', lw=1)


def run_new():
    t = time.time()
    planner.update_obstacle_map(areas, obstacles, [start, goal], deadline=time.time()+10.0)
    obstacle_map = planner.state.obstacle_map
    dt0 = time.time() - t

    t = time.time()

    min_x, min_y, size_x, size_y = obstacle_map.grid.bbox
    a = 2.0
    X, Y = np.meshgrid(
        np.arange(min_x, min_x + size_x - a / 2, a),
        np.arange(min_y, min_y + size_y, a * np.sqrt(3) / 2),
    )
    X[::2] += a / 2
    rows, cols = obstacle_map.grid.to_grid(X.flatten(), Y.flatten())
    free = [not all(obstacle_map.stack[int(np.round(row)), int(np.round(col)), :]) for row, col in zip(rows, cols)]
    points = np.stack((X.flatten(), Y.flatten()), axis=1)[free]

    @dataclass
    class PoseGroup:
        index: int
        point: Point
        neighbor_indices: list[int]
        poses: list[Pose]

    tri = spatial.Delaunay(points)

    def neighbors(i: int): return tri.vertex_neighbor_vertices[1][tri.vertex_neighbor_vertices[0][i]:
                                                                  tri.vertex_neighbor_vertices[0][i + 1]]
    pose_groups: list[PoseGroup] = [
        PoseGroup(
            index=i,
            point=Point(x=points[i, 0], y=points[i, 1]),
            neighbor_indices=neighbors(i),
            poses=[
                Pose(x=point[0], y=point[1], yaw=np.arctan2(neighbor[1] - point[1], neighbor[0] - point[0]))
                for neighbor in points[neighbors(i)]
            ]
        )
        for i, point in enumerate(points)
    ]

    G = nx.DiGraph()
    for g, group in enumerate(pose_groups):
        for p in range(len(group.poses)):
            G.add_node((g, p))
    for g, group in enumerate(pose_groups):
        for p, (pose, g_) in enumerate(zip(group.poses, group.neighbor_indices)):
            for p_, pose_ in enumerate(pose_groups[g_].poses):
                spline = Spline.from_poses(pose, pose_)
                if not obstacle_map.test_spline(spline):
                    G.add_edge((g, p), (g_, p_))

    dt1 = time.time() - t

    t = time.time()

    def estimate_length(spline: Spline) -> float:
        dx = np.diff([spline.x(t) for t in np.linspace(0, 1, 10)])
        dy = np.diff([spline.y(t) for t in np.linspace(0, 1, 10)])
        return np.sum(np.sqrt(dx**2 + dy**2))

    def find_terminal_segment(terminal_pose: Pose, first: bool) -> tuple[PathSegment, int, int]:
        terminal_point = terminal_pose
        group_distances = [g.point.distance(terminal_point) for g in pose_groups]
        group_indices = np.argsort(group_distances)
        for g, group in zip(group_indices, np.array(pose_groups)[group_indices]):
            best_result = None
            best_length = np.inf
            for p, pose in enumerate(group.poses):
                for backward in [False, True]:
                    poses = (terminal_pose, pose) if first else (pose, terminal_pose)
                    spline = Spline.from_poses(*poses, backward=backward)
                    if not obstacle_map.test_spline(spline, backward):
                        length = estimate_length(spline)
                        if length < best_length:
                            best_length = length
                            best_result = (PathSegment(spline=spline, backward=backward), g, p)
            if best_result is not None:
                return best_result

    first_segment, g, p = find_terminal_segment(start, True)
    last_segment, g_, p_ = find_terminal_segment(goal, False)

    path: list[PathSegment] = []
    path.append(first_segment)
    last_pose = pose_groups[g].poses[p]
    for path_g, path_p in nx.shortest_path(G, (g, p), (g_, p_))[1:]:
        next_pose = pose_groups[path_g].poses[path_p]
        spline = Spline.from_poses(last_pose, next_pose, backward=False)
        path.append(PathSegment(spline=spline, backward=False))
        last_pose = next_pose
    path.append(last_segment)

    dt2 = time.time() - t

    t = time.time()

    def is_healthy(spline: Spline, curvature_limit: float = 10.0):
        dir_ = spline.start.direction(spline.end)
        yaw0 = spline.start.direction(spline.control1)
        yaw1 = spline.control2.direction(spline.end)
        return \
            np.abs(angle(dir_, yaw0)) < np.pi / 2 and \
            np.abs(angle(dir_, yaw1)) < np.pi / 2 and \
            np.abs(spline.max_curvature()) < curvature_limit  # NOTE: max_curvature can be NaN

    while True:
        for s in range(len(path) - 1):
            new_start = Pose(
                x=path[s].spline.start.x,
                y=path[s].spline.start.y,
                yaw=path[s].spline.yaw(0) + (np.pi if path[s].backward else 0),
            )
            new_end = Pose(
                x=path[s+1].spline.end.x,
                y=path[s+1].spline.end.y,
                yaw=path[s+1].spline.yaw(1) + (np.pi if path[s+1].backward else 0),
            )
            new_backward = path[s+1].backward
            new_spline = Spline.from_poses(new_start, new_end, backward=new_backward)
            if not is_healthy(new_spline):
                continue
            if obstacle_map.test_spline(new_spline, new_backward):
                continue
            if .9 * estimate_length(new_spline) > estimate_length(path[s].spline) + estimate_length(path[s + 1].spline):
                continue
            path[s] = PathSegment(spline=new_spline, backward=new_backward)
            del path[s+1]
            break  # restart while loop
        else:
            break  # exit while loop

    dt3 = time.time() - t

    with plot:
        pl.clf()
        pl.title(f'map: {dt0:.3f} s, graph: {dt1:.3f} s, path: {dt2:.3f} s, smoothing: {dt3:.3f} s')
        pt.show_obstacle_map(obstacle_map)
        pl.gca().invert_yaxis()
        pl.autoscale(False)
        pl.triplot(points[:, 0], points[:, 1], tri.simplices, lw=0.1)

        pt.plot_path(path, 'C1')
        robot_renderer = RobotRenderer(robot_outline)
        pt.plot_robot(robot_renderer, (start.x, start.y, start.yaw), 'C0', lw=2)
        pt.plot_robot(robot_renderer, (goal.x, goal.y, goal.yaw), 'C0', lw=2)
        for step in path:
            for t in [0, 1]:
                yaw = step.spline.yaw(t) + np.pi if step.backward else step.spline.yaw(t)
                pt.plot_robot(robot_renderer, (step.spline.x(t), step.spline.y(t), yaw), 'C2', lw=1)


# run_old()
run_new()
with ui.row():
    ui.button('Run old', on_click=run_old)
    ui.button('Run new', on_click=run_new)

ui.run()
