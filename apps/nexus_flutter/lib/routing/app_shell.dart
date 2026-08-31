import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AppShell extends StatelessWidget {
  const AppShell({required this.navigationShell, super.key});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(child: navigationShell),
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        onDestinationSelected: (index) => navigationShell.goBranch(
          index,
          initialLocation: index == navigationShell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Home'),
          NavigationDestination(
            icon: Icon(Icons.route_outlined),
            label: 'Missions',
          ),
          NavigationDestination(
            icon: Icon(Icons.menu_book_outlined),
            label: 'Knowledge',
          ),
          NavigationDestination(
            icon: Icon(Icons.psychology_outlined),
            label: 'Memory',
          ),
          NavigationDestination(
            icon: Icon(Icons.tune_outlined),
            label: 'Settings',
          ),
        ],
      ),
    );
  }
}
