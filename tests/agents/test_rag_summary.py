from unittest.mock import MagicMock

from antbed.agents.rag_summary import LocalSummaryOutput, SummaryAgent, SummaryInput


def test_summary_agent_run():
    # Mock the OpenAI client
    mock_openai_client = MagicMock()

    # Mock the response from client.beta.chat.completions.parse
    mock_parsed_response = LocalSummaryOutput(
        short_version="shorter version",
        description="a description",
        title="a title",
        tags=["tag1"],
        language="en",
    )
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_response
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai_client.beta.chat.completions.parse.return_value = mock_response

    # Instantiate the agent with the mocked client
    agent = SummaryAgent(client=mock_openai_client)

    # Input for the agent
    input_data = SummaryInput(content="This is a long text to summarize.")

    # Run the agent
    result = agent.run(input_data)

    # Assertions
    assert result is not None
    assert result.short_version == "shorter version"
    assert result.title == "a title"
    assert result.language == "en"
    mock_openai_client.beta.chat.completions.parse.assert_called_once()
