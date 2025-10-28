from unittest.mock import MagicMock

from antbed.agents.rag_query import RagQuery, RagQueryAgent


def test_rag_query_agent_run():
    # Mock the OpenAI client
    mock_openai_client = MagicMock()

    # Mock the response from client.beta.chat.completions.parse
    mock_parsed_response = RagQuery(queries=["translated query1"], language="de")
    mock_choice = MagicMock()
    mock_choice.message.parsed = mock_parsed_response
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_openai_client.beta.chat.completions.parse.return_value = mock_response

    # Instantiate the agent with the mocked client
    agent = RagQueryAgent(client=mock_openai_client)

    # Input for the agent
    input_data = RagQuery(queries=["test query"], language="de")

    # Run the agent
    result = agent.run(input_data)

    # Assertions
    assert result is not None
    assert result.queries == ["translated query1"]
    assert result.language == "de"
    mock_openai_client.beta.chat.completions.parse.assert_called_once()
