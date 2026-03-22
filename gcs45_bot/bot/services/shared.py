from bot.services.claude_service import ClaudeService

# Единственный экземпляр на весь процесс — хранит историю диалогов
claude = ClaudeService()
