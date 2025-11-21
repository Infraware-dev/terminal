use infraware_terminal::executor::CommandExecutor;
use infraware_terminal::input::{InputClassifier, InputType};

#[test]
fn test_command_existence_check_before_interactive() {
    // Verify that requires_interactive returns true for interactive commands
    assert!(CommandExecutor::requires_interactive("htop"));
    assert!(CommandExecutor::requires_interactive("top"));
    assert!(CommandExecutor::requires_interactive("apt"));
    assert!(CommandExecutor::requires_interactive("vim"));

    // But command_exists should correctly report if they're installed
    // (this varies by system, so we just verify it doesn't panic)
    let _ = CommandExecutor::command_exists("htop");
    let _ = CommandExecutor::command_exists("top");
    let _ = CommandExecutor::command_exists("apt");
}

#[tokio::test]
async fn test_classification_preserves_interactive_commands() {
    // Verify that the input classifier correctly identifies interactive commands

    let classifier = InputClassifier::new();

    // apt is a known command (in DevOps whitelist)
    match classifier.classify("apt list").unwrap() {
        InputType::Command { command, args, .. } => {
            assert_eq!(command, "apt");
            assert_eq!(args, vec!["list"]);
        }
        other => panic!("Expected Command, got {:?}", other),
    }

    // htop is a known command
    match classifier.classify("htop").unwrap() {
        InputType::Command { command, args, .. } => {
            assert_eq!(command, "htop");
            assert!(args.is_empty());
        }
        other => panic!("Expected Command, got {:?}", other),
    }

    // top is a known command
    match classifier.classify("top").unwrap() {
        InputType::Command { command, args, .. } => {
            assert_eq!(command, "top");
            assert!(args.is_empty());
        }
        other => panic!("Expected Command, got {:?}", other),
    }
}
