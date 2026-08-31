import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:nexus_flutter/features/home/presentation/home_screen.dart';
import 'package:nexus_flutter/features/placeholder/presentation/placeholder_screen.dart';
import 'package:nexus_flutter/routing/app_shell.dart';

final appRouter = GoRouter(
  initialLocation: '/home',
  routes: [
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) =>
          AppShell(navigationShell: navigationShell),
      branches: [
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/home',
              builder: (context, state) => const HomeScreen(),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/missions',
              builder: (context, state) => const PlaceholderScreen(
                title: 'Missions',
                icon: Icons.route_outlined,
              ),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/knowledge',
              builder: (context, state) => const PlaceholderScreen(
                title: 'Knowledge',
                icon: Icons.menu_book_outlined,
              ),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/memory',
              builder: (context, state) => const PlaceholderScreen(
                title: 'Memory',
                icon: Icons.psychology_outlined,
              ),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/settings',
              builder: (context, state) => const PlaceholderScreen(
                title: 'Settings',
                icon: Icons.tune_outlined,
              ),
            ),
          ],
        ),
      ],
    ),
  ],
);
