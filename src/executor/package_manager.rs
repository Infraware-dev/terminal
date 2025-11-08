/// Package Manager Strategy Pattern
///
/// This module implements the Strategy pattern for package managers,
/// allowing easy extension with new package managers without modifying existing code.
use anyhow::Result;
use async_trait::async_trait;

use crate::executor::command::CommandExecutor;

/// Trait defining the interface for package managers
#[async_trait]
pub trait PackageManager: Send + Sync + std::fmt::Debug {
    /// Get the name of the package manager
    fn name(&self) -> &str;

    /// Check if this package manager is available on the system
    fn is_available(&self) -> bool;

    /// Install a package using this package manager
    async fn install(&self, package: &str) -> Result<()>;

    /// Get the priority of this package manager (higher = preferred)
    /// Useful for systems with multiple package managers
    fn priority(&self) -> u8;
}

/// APT package manager (Debian/Ubuntu)
#[derive(Debug, Clone, Copy)]
pub struct AptPackageManager;

#[async_trait]
impl PackageManager for AptPackageManager {
    fn name(&self) -> &str {
        "apt-get"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("apt-get")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute_sudo(
            "apt-get",
            &["install".to_string(), "-y".to_string(), package.to_string()],
        )
        .await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        80 // High priority on Debian/Ubuntu systems
    }
}

/// YUM package manager (RedHat/CentOS)
#[derive(Debug, Clone, Copy)]
pub struct YumPackageManager;

#[async_trait]
impl PackageManager for YumPackageManager {
    fn name(&self) -> &str {
        "yum"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("yum")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute_sudo(
            "yum",
            &["install".to_string(), "-y".to_string(), package.to_string()],
        )
        .await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        80
    }
}

/// DNF package manager (Fedora)
#[derive(Debug, Clone, Copy)]
pub struct DnfPackageManager;

#[async_trait]
impl PackageManager for DnfPackageManager {
    fn name(&self) -> &str {
        "dnf"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("dnf")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute_sudo(
            "dnf",
            &["install".to_string(), "-y".to_string(), package.to_string()],
        )
        .await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        85 // Prefer DNF over YUM on Fedora
    }
}

/// Pacman package manager (Arch Linux)
#[derive(Debug, Clone, Copy)]
pub struct PacmanPackageManager;

#[async_trait]
impl PackageManager for PacmanPackageManager {
    fn name(&self) -> &str {
        "pacman"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("pacman")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute_sudo(
            "pacman",
            &[
                "-S".to_string(),
                "--noconfirm".to_string(),
                package.to_string(),
            ],
        )
        .await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        80
    }
}

/// Homebrew package manager (macOS)
#[derive(Debug, Clone, Copy)]
pub struct BrewPackageManager;

#[async_trait]
impl PackageManager for BrewPackageManager {
    fn name(&self) -> &str {
        "brew"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("brew")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute("brew", &["install".to_string(), package.to_string()]).await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        90 // High priority on macOS
    }
}

/// Chocolatey package manager (Windows)
#[derive(Debug, Clone, Copy)]
pub struct ChocoPackageManager;

#[async_trait]
impl PackageManager for ChocoPackageManager {
    fn name(&self) -> &str {
        "choco"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("choco")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute(
            "choco",
            &["install".to_string(), "-y".to_string(), package.to_string()],
        )
        .await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        70
    }
}

/// Winget package manager (Windows)
#[derive(Debug, Clone, Copy)]
pub struct WingetPackageManager;

#[async_trait]
impl PackageManager for WingetPackageManager {
    fn name(&self) -> &str {
        "winget"
    }

    fn is_available(&self) -> bool {
        CommandExecutor::command_exists("winget")
    }

    async fn install(&self, package: &str) -> Result<()> {
        CommandExecutor::execute("winget", &["install".to_string(), package.to_string()]).await?;
        Ok(())
    }

    fn priority(&self) -> u8 {
        80 // Prefer winget over choco on modern Windows
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_package_manager_names() {
        assert_eq!(AptPackageManager.name(), "apt-get");
        assert_eq!(YumPackageManager.name(), "yum");
        assert_eq!(DnfPackageManager.name(), "dnf");
        assert_eq!(PacmanPackageManager.name(), "pacman");
        assert_eq!(BrewPackageManager.name(), "brew");
        assert_eq!(ChocoPackageManager.name(), "choco");
        assert_eq!(WingetPackageManager.name(), "winget");
    }

    #[test]
    fn test_package_manager_priorities() {
        // DNF should have higher priority than YUM
        assert!(DnfPackageManager.priority() > YumPackageManager.priority());

        // Winget should have higher priority than Choco
        assert!(WingetPackageManager.priority() > ChocoPackageManager.priority());
    }

    #[test]
    fn test_is_available() {
        // Just ensure the methods don't panic
        let managers: Vec<Box<dyn PackageManager>> = vec![
            Box::new(AptPackageManager),
            Box::new(YumPackageManager),
            Box::new(DnfPackageManager),
            Box::new(PacmanPackageManager),
            Box::new(BrewPackageManager),
            Box::new(ChocoPackageManager),
            Box::new(WingetPackageManager),
        ];

        for manager in managers {
            let _ = manager.is_available();
        }
    }
}
