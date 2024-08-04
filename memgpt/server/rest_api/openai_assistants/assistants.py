import uuid
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Path, Query
from pydantic import BaseModel, Field

from memgpt.constants import DEFAULT_PRESET
from memgpt.schemas.message import Message
from memgpt.schemas.openai.openai import (
    AssistantFile,
    MessageFile,
    MessageRoleType,
    OpenAIAssistant,
    OpenAIMessage,
    OpenAIRun,
    OpenAIRunStep,
    OpenAIThread,
    Text,
    ToolCall,
    ToolCallOutput,
)
from memgpt.server.rest_api.interface import QueuingInterface
from memgpt.server.server import SyncServer
from memgpt.utils import get_utc_time

router = APIRouter()


class CreateAssistantRequest(BaseModel):
    model: str = Field(..., description="The model to use for the assistant.")
    name: str = Field(..., description="The name of the assistant.")
    description: str = Field(None, description="The description of the assistant.")
    instructions: str = Field(..., description="The instructions for the assistant.")
    tools: List[str] = Field(None, description="The tools used by the assistant.")
    file_ids: List[str] = Field(None, description="List of file IDs associated with the assistant.")
    metadata: dict = Field(None, description="Metadata associated with the assistant.")

    # memgpt-only (not openai)
    embedding_model: str = Field(None, description="The model to use for the assistant.")

    ## TODO: remove
    # user_id: str = Field(..., description="The unique identifier of the user.")


class CreateThreadRequest(BaseModel):
    messages: Optional[List[str]] = Field(None, description="List of message IDs associated with the thread.")
    metadata: Optional[dict] = Field(None, description="Metadata associated with the thread.")

    # memgpt-only
    assistant_name: Optional[str] = Field(None, description="The name of the assistant (i.e. MemGPT preset)")


class ModifyThreadRequest(BaseModel):
    metadata: dict = Field(None, description="Metadata associated with the thread.")


class ModifyMessageRequest(BaseModel):
    metadata: dict = Field(None, description="Metadata associated with the message.")


class ModifyRunRequest(BaseModel):
    metadata: dict = Field(None, description="Metadata associated with the run.")


class CreateMessageRequest(BaseModel):
    role: str = Field(..., description="Role of the message sender (either 'user' or 'system')")
    content: str = Field(..., description="The message content to be processed by the agent.")
    file_ids: Optional[List[str]] = Field(None, description="List of file IDs associated with the message.")
    metadata: Optional[dict] = Field(None, description="Metadata associated with the message.")


class UserMessageRequest(BaseModel):
    user_id: str = Field(..., description="The unique identifier of the user.")
    agent_id: str = Field(..., description="The unique identifier of the agent.")
    message: str = Field(..., description="The message content to be processed by the agent.")
    stream: bool = Field(default=False, description="Flag to determine if the response should be streamed. Set to True for streaming.")
    role: MessageRoleType = Field(default=MessageRoleType.user, description="Role of the message sender (either 'user' or 'system')")


class UserMessageResponse(BaseModel):
    messages: List[dict] = Field(..., description="List of messages generated by the agent in response to the received message.")


class GetAgentMessagesRequest(BaseModel):
    user_id: str = Field(..., description="The unique identifier of the user.")
    agent_id: str = Field(..., description="The unique identifier of the agent.")
    start: int = Field(..., description="Message index to start on (reverse chronological).")
    count: int = Field(..., description="How many messages to retrieve.")


class ListMessagesResponse(BaseModel):
    messages: List[OpenAIMessage] = Field(..., description="List of message objects.")


class CreateAssistantFileRequest(BaseModel):
    file_id: str = Field(..., description="The unique identifier of the file.")


class CreateRunRequest(BaseModel):
    assistant_id: str = Field(..., description="The unique identifier of the assistant.")
    model: Optional[str] = Field(None, description="The model used by the run.")
    instructions: str = Field(..., description="The instructions for the run.")
    additional_instructions: Optional[str] = Field(None, description="Additional instructions for the run.")
    tools: Optional[List[ToolCall]] = Field(None, description="The tools used by the run (overrides assistant).")
    metadata: Optional[dict] = Field(None, description="Metadata associated with the run.")


class CreateThreadRunRequest(BaseModel):
    assistant_id: str = Field(..., description="The unique identifier of the assistant.")
    thread: OpenAIThread = Field(..., description="The thread to run.")
    model: str = Field(..., description="The model used by the run.")
    instructions: str = Field(..., description="The instructions for the run.")
    tools: Optional[List[ToolCall]] = Field(None, description="The tools used by the run (overrides assistant).")
    metadata: Optional[dict] = Field(None, description="Metadata associated with the run.")


class DeleteAssistantResponse(BaseModel):
    id: str = Field(..., description="The unique identifier of the agent.")
    object: str = "assistant.deleted"
    deleted: bool = Field(..., description="Whether the agent was deleted.")


class DeleteAssistantFileResponse(BaseModel):
    id: str = Field(..., description="The unique identifier of the file.")
    object: str = "assistant.file.deleted"
    deleted: bool = Field(..., description="Whether the file was deleted.")


class DeleteThreadResponse(BaseModel):
    id: str = Field(..., description="The unique identifier of the agent.")
    object: str = "thread.deleted"
    deleted: bool = Field(..., description="Whether the agent was deleted.")


class SubmitToolOutputsToRunRequest(BaseModel):
    tools_outputs: List[ToolCallOutput] = Field(..., description="The tool outputs to submit.")


# TODO: implement mechanism for creating/authenticating users associated with a bearer token
def setup_openai_assistant_router(server: SyncServer, interface: QueuingInterface):
    # create assistant (MemGPT agent)
    @router.post("/assistants", tags=["assistants"], response_model=OpenAIAssistant)
    def create_assistant(request: CreateAssistantRequest = Body(...)):
        # TODO: create preset
        return OpenAIAssistant(
            id=DEFAULT_PRESET,
            name="default_preset",
            description=request.description,
            created_at=int(get_utc_time().timestamp()),
            model=request.model,
            instructions=request.instructions,
            tools=request.tools,
            file_ids=request.file_ids,
            metadata=request.metadata,
        )

    @router.post("/assistants/{assistant_id}/files", tags=["assistants"], response_model=AssistantFile)
    def create_assistant_file(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
        request: CreateAssistantFileRequest = Body(...),
    ):
        # TODO: add file to assistant
        return AssistantFile(
            id=request.file_id,
            created_at=int(get_utc_time().timestamp()),
            assistant_id=assistant_id,
        )

    @router.get("/assistants", tags=["assistants"], response_model=List[OpenAIAssistant])
    def list_assistants(
        limit: int = Query(1000, description="How many assistants to retrieve."),
        order: str = Query("asc", description="Order of assistants to retrieve (either 'asc' or 'desc')."),
        after: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
        before: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
    ):
        # TODO: implement list assistants (i.e. list available MemGPT presets)
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/assistants/{assistant_id}/files", tags=["assistants"], response_model=List[AssistantFile])
    def list_assistant_files(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
        limit: int = Query(1000, description="How many files to retrieve."),
        order: str = Query("asc", description="Order of files to retrieve (either 'asc' or 'desc')."),
        after: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
        before: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
    ):
        # TODO: list attached data sources to preset
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/assistants/{assistant_id}", tags=["assistants"], response_model=OpenAIAssistant)
    def retrieve_assistant(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
    ):
        # TODO: get and return preset
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/assistants/{assistant_id}/files/{file_id}", tags=["assistants"], response_model=AssistantFile)
    def retrieve_assistant_file(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
        file_id: str = Path(..., description="The unique identifier of the file."),
    ):
        # TODO: return data source attached to preset
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/assistants/{assistant_id}", tags=["assistants"], response_model=OpenAIAssistant)
    def modify_assistant(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
        request: CreateAssistantRequest = Body(...),
    ):
        # TODO: modify preset
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.delete("/assistants/{assistant_id}", tags=["assistants"], response_model=DeleteAssistantResponse)
    def delete_assistant(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
    ):
        # TODO: delete preset
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.delete("/assistants/{assistant_id}/files/{file_id}", tags=["assistants"], response_model=DeleteAssistantFileResponse)
    def delete_assistant_file(
        assistant_id: str = Path(..., description="The unique identifier of the assistant."),
        file_id: str = Path(..., description="The unique identifier of the file."),
    ):
        # TODO: delete source on preset
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads", tags=["threads"], response_model=OpenAIThread)
    def create_thread(request: CreateThreadRequest = Body(...)):
        # TODO: use requests.description and requests.metadata fields
        # TODO: handle requests.file_ids and requests.tools
        # TODO: eventually allow request to override embedding/llm model

        print("Create thread/agent", request)
        # create a memgpt agent
        agent_state = server.create_agent(
            user_id=user_id,
        )
        # TODO: insert messages into recall memory
        return OpenAIThread(
            id=str(agent_state.id),
            created_at=int(agent_state.created_at.timestamp()),
        )

    @router.get("/threads/{thread_id}", tags=["threads"], response_model=OpenAIThread)
    def retrieve_thread(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
    ):
        agent = server.get_agent(uuid.UUID(thread_id))
        return OpenAIThread(
            id=str(agent.id),
            created_at=int(agent.created_at.timestamp()),
        )

    @router.get("/threads/{thread_id}", tags=["threads"], response_model=OpenAIThread)
    def modify_thread(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        request: ModifyThreadRequest = Body(...),
    ):
        # TODO: add agent metadata so this can be modified
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.delete("/threads/{thread_id}", tags=["threads"], response_model=DeleteThreadResponse)
    def delete_thread(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
    ):
        # TODO: delete agent
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads/{thread_id}/messages", tags=["messages"], response_model=OpenAIMessage)
    def create_message(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        request: CreateMessageRequest = Body(...),
    ):
        agent_id = uuid.UUID(thread_id)
        # create message object
        message = Message(
            user_id=user_id,
            agent_id=agent_id,
            role=request.role,
            text=request.content,
        )
        agent = server._get_or_load_agent(user_id=user_id, agent_id=agent_id)
        # add message to agent
        agent._append_to_messages([message])

        openai_message = OpenAIMessage(
            id=str(message.id),
            created_at=int(message.created_at.timestamp()),
            content=[Text(text=message.text)],
            role=message.role,
            thread_id=str(message.agent_id),
            assistant_id=DEFAULT_PRESET,  # TODO: update this
            # file_ids=message.file_ids,
            # metadata=message.metadata,
        )
        return openai_message

    @router.get("/threads/{thread_id}/messages", tags=["messages"], response_model=ListMessagesResponse)
    def list_messages(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        limit: int = Query(1000, description="How many messages to retrieve."),
        order: str = Query("asc", description="Order of messages to retrieve (either 'asc' or 'desc')."),
        after: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
        before: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
    ):
        after_uuid = uuid.UUID(after) if before else None
        before_uuid = uuid.UUID(before) if before else None
        agent_id = uuid.UUID(thread_id)
        reverse = True if (order == "desc") else False
        cursor, json_messages = server.get_agent_recall_cursor(
            user_id=user_id,
            agent_id=agent_id,
            limit=limit,
            after=after_uuid,
            before=before_uuid,
            order_by="created_at",
            reverse=reverse,
        )
        print(json_messages[0]["text"])
        # convert to openai style messages
        openai_messages = [
            OpenAIMessage(
                id=str(message["id"]),
                created_at=int(message["created_at"].timestamp()),
                content=[Text(text=message["text"])],
                role=message["role"],
                thread_id=str(message["agent_id"]),
                assistant_id=DEFAULT_PRESET,  # TODO: update this
                # file_ids=message.file_ids,
                # metadata=message.metadata,
            )
            for message in json_messages
        ]
        print("MESSAGES", openai_messages)
        # TODO: cast back to message objects
        return ListMessagesResponse(messages=openai_messages)

    router.get("/threads/{thread_id}/messages/{message_id}", tags=["messages"], response_model=OpenAIMessage)

    def retrieve_message(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        message_id: str = Path(..., description="The unique identifier of the message."),
    ):
        message_id = uuid.UUID(message_id)
        agent_id = uuid.UUID(thread_id)
        message = server.get_agent_message(agent_id, message_id)
        return OpenAIMessage(
            id=str(message.id),
            created_at=int(message.created_at.timestamp()),
            content=[Text(text=message.text)],
            role=message.role,
            thread_id=str(message.agent_id),
            assistant_id=DEFAULT_PRESET,  # TODO: update this
            # file_ids=message.file_ids,
            # metadata=message.metadata,
        )

    @router.get("/threads/{thread_id}/messages/{message_id}/files/{file_id}", tags=["messages"], response_model=MessageFile)
    def retrieve_message_file(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        message_id: str = Path(..., description="The unique identifier of the message."),
        file_id: str = Path(..., description="The unique identifier of the file."),
    ):
        # TODO: implement?
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads/{thread_id}/messages/{message_id}", tags=["messages"], response_model=OpenAIMessage)
    def modify_message(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        message_id: str = Path(..., description="The unique identifier of the message."),
        request: ModifyMessageRequest = Body(...),
    ):
        # TODO: add metada field to message so this can be modified
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads/{thread_id}/runs", tags=["runs"], response_model=OpenAIRun)
    def create_run(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        request: CreateRunRequest = Body(...),
    ):
        # TODO: add request.instructions as a message?
        agent_id = uuid.UUID(thread_id)
        # TODO: override preset of agent with request.assistant_id
        agent = server._get_or_load_agent(user_id=user_id, agent_id=agent_id)
        agent.step(user_message=None)  # already has messages added
        run_id = str(uuid.uuid4())
        create_time = int(get_utc_time().timestamp())
        return OpenAIRun(
            id=run_id,
            created_at=create_time,
            thread_id=str(agent_id),
            assistant_id=DEFAULT_PRESET,  # TODO: update this
            status="completed",  # TODO: eventaully allow offline execution
            expires_at=create_time,
            model=agent.agent_state.llm_config.model,
            instructions=request.instructions,
        )

    @router.post("/threads/runs", tags=["runs"], response_model=OpenAIRun)
    def create_thread_and_run(
        request: CreateThreadRunRequest = Body(...),
    ):
        # TODO: add a bunch of messages and execute
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/threads/{thread_id}/runs", tags=["runs"], response_model=List[OpenAIRun])
    def list_runs(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        limit: int = Query(1000, description="How many runs to retrieve."),
        order: str = Query("asc", description="Order of runs to retrieve (either 'asc' or 'desc')."),
        after: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
        before: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
    ):
        # TODO: store run information in a DB so it can be returned here
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/threads/{thread_id}/runs/{run_id}/steps", tags=["runs"], response_model=List[OpenAIRunStep])
    def list_run_steps(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        run_id: str = Path(..., description="The unique identifier of the run."),
        limit: int = Query(1000, description="How many run steps to retrieve."),
        order: str = Query("asc", description="Order of run steps to retrieve (either 'asc' or 'desc')."),
        after: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
        before: str = Query(
            None, description="A cursor for use in pagination. `after` is an object ID that defines your place in the list."
        ),
    ):
        # TODO: store run information in a DB so it can be returned here
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/threads/{thread_id}/runs/{run_id}", tags=["runs"], response_model=OpenAIRun)
    def retrieve_run(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        run_id: str = Path(..., description="The unique identifier of the run."),
    ):
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.get("/threads/{thread_id}/runs/{run_id}/steps/{step_id}", tags=["runs"], response_model=OpenAIRunStep)
    def retrieve_run_step(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        run_id: str = Path(..., description="The unique identifier of the run."),
        step_id: str = Path(..., description="The unique identifier of the run step."),
    ):
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads/{thread_id}/runs/{run_id}", tags=["runs"], response_model=OpenAIRun)
    def modify_run(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        run_id: str = Path(..., description="The unique identifier of the run."),
        request: ModifyRunRequest = Body(...),
    ):
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads/{thread_id}/runs/{run_id}/submit_tool_outputs", tags=["runs"], response_model=OpenAIRun)
    def submit_tool_outputs_to_run(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        run_id: str = Path(..., description="The unique identifier of the run."),
        request: SubmitToolOutputsToRunRequest = Body(...),
    ):
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    @router.post("/threads/{thread_id}/runs/{run_id}/cancel", tags=["runs"], response_model=OpenAIRun)
    def cancel_run(
        thread_id: str = Path(..., description="The unique identifier of the thread."),
        run_id: str = Path(..., description="The unique identifier of the run."),
    ):
        raise HTTPException(status_code=404, detail="Not yet implemented (coming soon)")

    return router
