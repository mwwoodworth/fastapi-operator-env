/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Body_auth_token_auth_token_post } from '../models/Body_auth_token_auth_token_post';
import type { Body_upload_file_files_post } from '../models/Body_upload_file_files_post';
import type { Body_voice_upload_voice_upload_post } from '../models/Body_voice_upload_voice_upload_post';
import type { CeleryTaskResponse } from '../models/CeleryTaskResponse';
import type { ChatRequest } from '../models/ChatRequest';
import type { ChatResponse } from '../models/ChatResponse';
import type { ChatToTaskRequest } from '../models/ChatToTaskRequest';
import type { CoAuthorRequest } from '../models/CoAuthorRequest';
import type { DelayRequest } from '../models/DelayRequest';
import type { DependencyMapRequest } from '../models/DependencyMapRequest';
import type { DocumentUpdateResponse } from '../models/DocumentUpdateResponse';
import type { DocumentWriteResponse } from '../models/DocumentWriteResponse';
import type { FeedbackReport } from '../models/FeedbackReport';
import type { GeminiRowInput } from '../models/GeminiRowInput';
import type { InboxDecision } from '../models/InboxDecision';
import type { KnowledgeDocUploadRequest } from '../models/KnowledgeDocUploadRequest';
import type { KnowledgeDocUploadResponse } from '../models/KnowledgeDocUploadResponse';
import type { KnowledgeQueryRequest } from '../models/KnowledgeQueryRequest';
import type { KnowledgeSearchResponse } from '../models/KnowledgeSearchResponse';
import type { LongTaskRequest } from '../models/LongTaskRequest';
import type { MemoryDiffRequest } from '../models/MemoryDiffRequest';
import type { MemoryEntriesResponse } from '../models/MemoryEntriesResponse';
import type { MemoryTraceResponse } from '../models/MemoryTraceResponse';
import type { MessageCreate } from '../models/MessageCreate';
import type { MessageUpdate } from '../models/MessageUpdate';
import type { MobileTask } from '../models/MobileTask';
import type { NLDesignRequest } from '../models/NLDesignRequest';
import type { PageCreatePayload } from '../models/PageCreatePayload';
import type { PageUpdatePayload } from '../models/PageUpdatePayload';
import type { QueryInput } from '../models/QueryInput';
import type { QueryResultsResponse } from '../models/QueryResultsResponse';
import type { RecurringTask } from '../models/RecurringTask';
import type { RelayInput } from '../models/RelayInput';
import type { StatusResponse } from '../models/StatusResponse';
import type { StatusUpdate } from '../models/StatusUpdate';
import type { TanaNodeCreateResponse } from '../models/TanaNodeCreateResponse';
import type { TanaRequest } from '../models/TanaRequest';
import type { TaskCreate } from '../models/TaskCreate';
import type { TaskPayload } from '../models/TaskPayload';
import type { TaskRunRequest } from '../models/TaskRunRequest';
import type { TaskRunResponse } from '../models/TaskRunResponse';
import type { TaskUpdate } from '../models/TaskUpdate';
import type { ThreadCreate } from '../models/ThreadCreate';
import type { ThreadUpdate } from '../models/ThreadUpdate';
import type { UpdateInput } from '../models/UpdateInput';
import type { UpdatePayload } from '../models/UpdatePayload';
import type { ValueResponse } from '../models/ValueResponse';
import type { VoiceHistoryResponse } from '../models/VoiceHistoryResponse';
import type { VoiceStatusResponse } from '../models/VoiceStatusResponse';
import type { VoiceTraceResponse } from '../models/VoiceTraceResponse';
import type { VoiceUploadResponse } from '../models/VoiceUploadResponse';
import type { WriteInput } from '../models/WriteInput';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DefaultService {
    /**
     * Handle Webhook
     * @returns any Successful Response
     * @throws ApiError
     */
    public static handleWebhookWebhookMakePost({
        requestBody,
        xMakeSecret,
    }: {
        requestBody: Record<string, any>,
        xMakeSecret?: (string | null),
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/webhook/make',
            headers: {
                'x-make-secret': xMakeSecret,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Create Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiCreateTaskClickupTasksPost({
        requestBody,
    }: {
        requestBody: TaskPayload,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/clickup/tasks',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Get Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiGetTaskClickupTasksTaskIdGet({
        taskId,
        token,
        workspace,
    }: {
        taskId: string,
        token: string,
        workspace: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/clickup/tasks/{task_id}',
            path: {
                'task_id': taskId,
            },
            query: {
                'token': token,
                'workspace': workspace,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Update Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiUpdateTaskClickupTasksTaskIdPut({
        taskId,
        requestBody,
    }: {
        taskId: string,
        requestBody: UpdatePayload,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/clickup/tasks/{task_id}',
            path: {
                'task_id': taskId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Delete Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiDeleteTaskClickupTasksTaskIdDelete({
        taskId,
        token,
        workspace,
    }: {
        taskId: string,
        token: string,
        workspace: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/clickup/tasks/{task_id}',
            path: {
                'task_id': taskId,
            },
            query: {
                'token': token,
                'workspace': workspace,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Search Tasks
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiSearchTasksClickupTasksSearchGet({
        token,
        workspace,
        query,
    }: {
        token: string,
        workspace: string,
        query: string,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/clickup/tasks/search',
            query: {
                'token': token,
                'workspace': workspace,
                'query': query,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Webhook
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiWebhookClickupWebhookPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/clickup/webhook',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Create Page
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiCreatePageNotionPagesPost({
        requestBody,
    }: {
        requestBody: PageCreatePayload,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/notion/pages',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Get Page
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiGetPageNotionPagesPageIdGet({
        pageId,
        token,
        workspace,
    }: {
        pageId: string,
        token: string,
        workspace: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/notion/pages/{page_id}',
            path: {
                'page_id': pageId,
            },
            query: {
                'token': token,
                'workspace': workspace,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Update Page
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiUpdatePageNotionPagesPageIdPatch({
        pageId,
        requestBody,
    }: {
        pageId: string,
        requestBody: PageUpdatePayload,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/notion/pages/{page_id}',
            path: {
                'page_id': pageId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Delete Page
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiDeletePageNotionPagesPageIdDelete({
        pageId,
        token,
        workspace,
    }: {
        pageId: string,
        token: string,
        workspace: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/notion/pages/{page_id}',
            path: {
                'page_id': pageId,
            },
            query: {
                'token': token,
                'workspace': workspace,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Search Pages
     * @returns string Successful Response
     * @throws ApiError
     */
    public static apiSearchPagesNotionPagesSearchGet({
        token,
        workspace,
        query,
    }: {
        token: string,
        workspace: string,
        query: string,
    }): CancelablePromise<Array<Record<string, string>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/notion/pages/search',
            query: {
                'token': token,
                'workspace': workspace,
                'query': query,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Page Snippet
     * @returns string Successful Response
     * @throws ApiError
     */
    public static apiPageSnippetNotionPagesPageIdSnippetGet({
        pageId,
        token,
        workspace,
    }: {
        pageId: string,
        token: string,
        workspace: string,
    }): CancelablePromise<string> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/notion/pages/{page_id}/snippet',
            path: {
                'page_id': pageId,
            },
            query: {
                'token': token,
                'workspace': workspace,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Api Webhook
     * @returns any Successful Response
     * @throws ApiError
     */
    public static apiWebhookNotionWebhookPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/notion/webhook',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Query Memory
     * Vector search fallback to keyword match.
     * @returns QueryResultsResponse Successful Response
     * @throws ApiError
     */
    public static queryMemoryMemoryQueryPost({
        requestBody,
    }: {
        requestBody: QueryInput,
    }): CancelablePromise<QueryResultsResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/query',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Memory Query
     * @returns MemoryEntriesResponse Successful Response
     * @throws ApiError
     */
    public static memoryQueryMemoryQueryGet({
        tags = '',
        limit = 10,
    }: {
        tags?: string,
        limit?: number,
    }): CancelablePromise<MemoryEntriesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/memory/query',
            query: {
                'tags': tags,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Write Memory
     * Create project/agent if needed and store document chunks.
     * @returns DocumentWriteResponse Successful Response
     * @throws ApiError
     */
    public static writeMemoryMemoryWritePost({
        requestBody,
    }: {
        requestBody: WriteInput,
    }): CancelablePromise<DocumentWriteResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/write',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Memory
     * Replace document content and re-embed.
     * @returns DocumentUpdateResponse Successful Response
     * @throws ApiError
     */
    public static updateMemoryMemoryUpdatePost({
        requestBody,
    }: {
        requestBody: UpdateInput,
    }): CancelablePromise<DocumentUpdateResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/update',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Relay Handler
     * Generic relay endpoint for external sources.
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static relayHandlerMemoryRelayPost({
        requestBody,
    }: {
        requestBody: RelayInput,
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/relay',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Gemini Sync
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static geminiSyncMemoryGeminiSyncPost({
        requestBody,
        xWebhookSecret,
    }: {
        requestBody: GeminiRowInput,
        xWebhookSecret?: (string | null),
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/gemini-sync',
            headers: {
                'x-webhook-secret': xWebhookSecret,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Gemini Webhook
     * @returns any Successful Response
     * @throws ApiError
     */
    public static geminiWebhookGeminiWebhookPost({
        requestBody,
        xWebhookSecret,
    }: {
        requestBody: GeminiRowInput,
        xWebhookSecret?: (string | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/gemini/webhook',
            headers: {
                'x-webhook-secret': xWebhookSecret,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Threads
     * Return all threads.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listThreadsThreadsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/threads',
        });
    }
    /**
     * Create Thread
     * Create a new chat thread.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static createThreadThreadsPost({
        requestBody,
    }: {
        requestBody: ThreadCreate,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/threads',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Thread
     * Fetch a single thread by ID.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getThreadThreadsThreadIdGet({
        threadId,
    }: {
        threadId: number,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/threads/{thread_id}',
            path: {
                'thread_id': threadId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Thread
     * Update thread title or participants.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateThreadThreadsThreadIdPatch({
        threadId,
        requestBody,
    }: {
        threadId: number,
        requestBody: ThreadUpdate,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/threads/{thread_id}',
            path: {
                'thread_id': threadId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Message
     * Create a message in a thread.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static createMessageMessagesPost({
        requestBody,
    }: {
        requestBody: MessageCreate,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/messages',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Messages
     * List messages filtered by thread or sender.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listMessagesMessagesGet({
        thread,
        sender,
    }: {
        thread?: (number | null),
        sender?: (string | null),
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/messages',
            query: {
                'thread': thread,
                'sender': sender,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Edit Message
     * Edit message content or metadata.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static editMessageMessagesMessageIdPatch({
        messageId,
        requestBody,
    }: {
        messageId: number,
        requestBody: MessageUpdate,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/messages/{message_id}',
            path: {
                'message_id': messageId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Message
     * Delete a message.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteMessageMessagesMessageIdDelete({
        messageId,
    }: {
        messageId: number,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/messages/{message_id}',
            path: {
                'message_id': messageId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Create Task
     * Create a task.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static createTaskTasksPost({
        requestBody,
    }: {
        requestBody: TaskCreate,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/tasks',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Tasks
     * List tasks filtered by assigned user, status or thread.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listTasksTasksGet({
        assignedTo,
        status,
        thread,
    }: {
        assignedTo?: (string | null),
        status?: (string | null),
        thread?: (number | null),
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/tasks',
            query: {
                'assigned_to': assignedTo,
                'status': status,
                'thread': thread,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Update Task
     * Update task fields.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static updateTaskTasksTaskIdPatch({
        taskId,
        requestBody,
    }: {
        taskId: number,
        requestBody: TaskUpdate,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PATCH',
            url: '/tasks/{task_id}',
            path: {
                'task_id': taskId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Task
     * Delete a task.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteTaskTasksTaskIdDelete({
        taskId,
    }: {
        taskId: number,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/tasks/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Upload File
     * Upload a file and store metadata.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static uploadFileFilesPost({
        formData,
    }: {
        formData: Body_upload_file_files_post,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/files',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Files
     * List uploaded files filtered by thread or task.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listFilesFilesGet({
        thread,
        task,
    }: {
        thread?: (number | null),
        task?: (number | null),
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/files',
            query: {
                'thread': thread,
                'task': task,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete File
     * Delete a stored file and remove from disk.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static deleteFileFilesFileIdDelete({
        fileId,
    }: {
        fileId: number,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/files/{file_id}',
            path: {
                'file_id': fileId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Auth Token
     * @returns any Successful Response
     * @throws ApiError
     */
    public static authTokenAuthTokenPost({
        formData,
    }: {
        formData: Body_auth_token_auth_token_post,
    }): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/auth/token',
            formData: formData,
            mediaType: 'application/x-www-form-urlencoded',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Refresh Access Token
     * @returns any Successful Response
     * @throws ApiError
     */
    public static refreshAccessTokenAuthRefreshPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/auth/refresh',
        });
    }
    /**
     * Logout
     * @returns any Successful Response
     * @throws ApiError
     */
    public static logoutAuthLogoutPost(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/auth/logout',
        });
    }
    /**
     * Create Tana Node
     * Create a note in Tana from the provided content.
     * @returns TanaNodeCreateResponse Successful Response
     * @throws ApiError
     */
    public static createTanaNodeTanaCreateNodePost({
        requestBody,
    }: {
        requestBody: TanaRequest,
    }): CancelablePromise<TanaNodeCreateResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/tana/create-node',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Task Run
     * @returns CeleryTaskResponse Successful Response
     * @throws ApiError
     */
    public static taskRunTaskRunPost({
        requestBody,
    }: {
        requestBody: TaskRunRequest,
    }): CancelablePromise<CeleryTaskResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/task/run',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Generate Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static generateTaskTaskGeneratePost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/task/generate',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Nl Design
     * @returns any Successful Response
     * @throws ApiError
     */
    public static nlDesignTaskNlDesignPost({
        requestBody,
    }: {
        requestBody: NLDesignRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/task/nl-design',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Queue Long Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static queueLongTaskTasksLongPost({
        requestBody,
    }: {
        requestBody: LongTaskRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/tasks/long',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Task Status
     * @returns any Successful Response
     * @throws ApiError
     */
    public static taskStatusTaskStatusTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/task/status/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Task Status
     * @returns any Successful Response
     * @throws ApiError
     */
    public static taskStatusTasksStatusTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/tasks/status/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Chat Endpoint
     * @returns ChatResponse Successful Response
     * @throws ApiError
     */
    public static chatEndpointChatPost({
        requestBody,
    }: {
        requestBody: ChatRequest,
    }): CancelablePromise<ChatResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/chat',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Chat To Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static chatToTaskChatToTaskPost({
        requestBody,
    }: {
        requestBody: ChatToTaskRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/chat/to-task',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Webhook Trigger
     * @returns TaskRunResponse Successful Response
     * @throws ApiError
     */
    public static webhookTriggerTaskWebhookPost({
        requestBody,
        xWebhookSecret,
    }: {
        requestBody: Record<string, any>,
        xWebhookSecret?: (string | null),
    }): CancelablePromise<TaskRunResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/task/webhook',
            headers: {
                'x-webhook-secret': xWebhookSecret,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Github Webhook
     * @returns any Successful Response
     * @throws ApiError
     */
    public static githubWebhookWebhookGithubPost({
        xHubSignature256,
    }: {
        xHubSignature256?: (string | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/webhook/github',
            headers: {
                'x-hub-signature-256': xHubSignature256,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Stripe Webhook
     * Handle Stripe sale events and enqueue ``sync_sale`` task.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static stripeWebhookWebhookStripePost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/webhook/stripe',
        });
    }
    /**
     * Slack Command
     * Process Slack slash-command approvals for inbox tasks.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static slackCommandWebhookSlackCommandPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/webhook/slack/command',
        });
    }
    /**
     * Slack Event
     * Handle generic Slack Events API payloads.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static slackEventWebhookSlackEventPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/webhook/slack/event',
        });
    }
    /**
     * Inspect Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static inspectTaskTaskInspectTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/task/inspect/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Docs Registry
     * @returns any Successful Response
     * @throws ApiError
     */
    public static docsRegistryDocsRegistryGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/docs/registry',
        });
    }
    /**
     * Store Secret Api
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static storeSecretApiSecretsStorePost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/secrets/store',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Retrieve Secret Api
     * @returns ValueResponse Successful Response
     * @throws ApiError
     */
    public static retrieveSecretApiSecretsRetrieveNameGet({
        name,
    }: {
        name: string,
    }): CancelablePromise<ValueResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/secrets/retrieve/{name}',
            path: {
                'name': name,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Secret Api
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static deleteSecretApiSecretsDeleteNameDelete({
        name,
    }: {
        name: string,
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/secrets/delete/{name}',
            path: {
                'name': name,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Secrets Api
     * @returns any Successful Response
     * @throws ApiError
     */
    public static listSecretsApiSecretsListGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/secrets/list',
        });
    }
    /**
     * Memory Summary
     * @returns any Successful Response
     * @throws ApiError
     */
    public static memorySummaryMemorySummaryGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/memory/summary',
        });
    }
    /**
     * Memory Search
     * @returns MemoryEntriesResponse Successful Response
     * @throws ApiError
     */
    public static memorySearchMemorySearchGet({
        q = '',
        tags = '',
        start,
        end,
        user,
        limit = 20,
    }: {
        q?: string,
        tags?: string,
        start?: (string | null),
        end?: (string | null),
        user?: (string | null),
        limit?: number,
    }): CancelablePromise<MemoryEntriesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/memory/search',
            query: {
                'q': q,
                'tags': tags,
                'start': start,
                'end': end,
                'user': user,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Knowledge Index
     * @returns any Successful Response
     * @throws ApiError
     */
    public static knowledgeIndexKnowledgeIndexPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/knowledge/index',
        });
    }
    /**
     * Knowledge Query
     * @returns any Successful Response
     * @throws ApiError
     */
    public static knowledgeQueryKnowledgeQueryPost({
        requestBody,
    }: {
        requestBody: KnowledgeQueryRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/knowledge/query',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Knowledge Sources
     * @returns any Successful Response
     * @throws ApiError
     */
    public static knowledgeSourcesKnowledgeSourcesGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/knowledge/sources',
        });
    }
    /**
     * Knowledge Doc Upload
     * @returns KnowledgeDocUploadResponse Successful Response
     * @throws ApiError
     */
    public static knowledgeDocUploadKnowledgeDocUploadPost({
        requestBody,
    }: {
        requestBody: KnowledgeDocUploadRequest,
    }): CancelablePromise<KnowledgeDocUploadResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/knowledge/doc/upload',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Knowledge Search
     * @returns KnowledgeSearchResponse Successful Response
     * @throws ApiError
     */
    public static knowledgeSearchKnowledgeSearchGet({
        q,
        limit = 5,
    }: {
        q: string,
        limit?: number,
    }): CancelablePromise<KnowledgeSearchResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/knowledge/search',
            query: {
                'q': q,
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Rag Logs
     * @returns MemoryEntriesResponse Successful Response
     * @throws ApiError
     */
    public static ragLogsLogsRagGet({
        limit = 20,
    }: {
        limit?: number,
    }): CancelablePromise<MemoryEntriesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/logs/rag',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Error Logs
     * Return recent error log entries.
     * @returns MemoryEntriesResponse Successful Response
     * @throws ApiError
     */
    public static errorLogsLogsErrorsGet({
        limit = 50,
    }: {
        limit?: number,
    }): CancelablePromise<MemoryEntriesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/logs/errors',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Feedback Report
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static feedbackReportFeedbackReportPost({
        requestBody,
    }: {
        requestBody: FeedbackReport,
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/feedback/report',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Memory Trace
     * @returns MemoryTraceResponse Successful Response
     * @throws ApiError
     */
    public static memoryTraceMemoryTraceTaskIdGet({
        taskId,
    }: {
        taskId: string,
    }): CancelablePromise<MemoryTraceResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/memory/trace/{task_id}',
            path: {
                'task_id': taskId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Chat History
     * @returns MemoryEntriesResponse Successful Response
     * @throws ApiError
     */
    public static chatHistoryChatHistoryGet({
        limit = 20,
        model,
        tags = '',
        sessionId,
    }: {
        limit?: number,
        model?: (string | null),
        tags?: string,
        sessionId?: (string | null),
    }): CancelablePromise<MemoryEntriesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/chat/history',
            query: {
                'limit': limit,
                'model': model,
                'tags': tags,
                'session_id': sessionId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Voice Upload
     * Upload an audio file and process it into tasks.
     * @returns VoiceUploadResponse Successful Response
     * @throws ApiError
     */
    public static voiceUploadVoiceUploadPost({
        formData,
    }: {
        formData: Body_voice_upload_voice_upload_post,
    }): CancelablePromise<VoiceUploadResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/voice/upload',
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Voice History
     * @returns VoiceHistoryResponse Successful Response
     * @throws ApiError
     */
    public static voiceHistoryVoiceHistoryGet({
        limit = 20,
    }: {
        limit?: number,
    }): CancelablePromise<VoiceHistoryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/voice/history',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Voice Trace
     * @returns VoiceTraceResponse Successful Response
     * @throws ApiError
     */
    public static voiceTraceVoiceTraceTranscriptIdGet({
        transcriptId,
    }: {
        transcriptId: string,
    }): CancelablePromise<VoiceTraceResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/voice/trace/{transcript_id}',
            path: {
                'transcript_id': transcriptId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Voice Status
     * @returns VoiceStatusResponse Successful Response
     * @throws ApiError
     */
    public static voiceStatusVoiceStatusGet(): CancelablePromise<VoiceStatusResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/voice/status',
        });
    }
    /**
     * Status Update
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static statusUpdateWebhookStatusUpdatePost({
        requestBody,
        xWebhookSecret,
    }: {
        requestBody: StatusUpdate,
        xWebhookSecret?: (string | null),
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/webhook/status-update',
            headers: {
                'x-webhook-secret': xWebhookSecret,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Agent Inbox View
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentInboxViewAgentInboxGet({
        limit = 10,
    }: {
        limit?: number,
    }): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/agent/inbox',
            query: {
                'limit': limit,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Agent Inbox Approve
     * @returns TaskRunResponse Successful Response
     * @throws ApiError
     */
    public static agentInboxApproveAgentInboxApprovePost({
        requestBody,
    }: {
        requestBody: InboxDecision,
    }): CancelablePromise<TaskRunResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/inbox/approve',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Agent Inbox Delay
     * @returns StatusResponse Successful Response
     * @throws ApiError
     */
    public static agentInboxDelayAgentInboxDelayPost({
        requestBody,
    }: {
        requestBody: DelayRequest,
    }): CancelablePromise<StatusResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/inbox/delay',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Agent Inbox Summary
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentInboxSummaryAgentInboxSummaryGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/agent/inbox/summary',
        });
    }
    /**
     * Agent Daily Plan
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentDailyPlanAgentPlanDailyPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/plan/daily',
        });
    }
    /**
     * Agent Inbox Prioritize
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentInboxPrioritizeAgentInboxPrioritizePost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/inbox/prioritize',
        });
    }
    /**
     * Agent Inbox Mobile
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentInboxMobileAgentInboxMobileGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/agent/inbox/mobile',
        });
    }
    /**
     * Optimize Flow
     * @returns any Successful Response
     * @throws ApiError
     */
    public static optimizeFlowOptimizeFlowPost({
        requestBody,
    }: {
        requestBody: Record<string, any>,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/optimize/flow',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Memory Sync Agents
     * @returns any Successful Response
     * @throws ApiError
     */
    public static memorySyncAgentsMemorySyncAgentsPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/sync/agents',
        });
    }
    /**
     * Memory Audit Diff
     * @returns any Successful Response
     * @throws ApiError
     */
    public static memoryAuditDiffMemoryAuditDiffPost({
        requestBody,
    }: {
        requestBody: MemoryDiffRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/memory/audit/diff',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Task Ai Coauthor
     * @returns any Successful Response
     * @throws ApiError
     */
    public static taskAiCoauthorTaskAiCoauthorPost({
        requestBody,
    }: {
        requestBody: CoAuthorRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/task/ai-coauthor',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Workflows Audit
     * @returns any Successful Response
     * @throws ApiError
     */
    public static workflowsAuditAgentWorkflowsAuditPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/workflows/audit',
        });
    }
    /**
     * Agent Forecast Weekly
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentForecastWeeklyAgentForecastWeeklyPost({
        requestBody,
    }: {
        requestBody?: (Record<string, any> | null),
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/forecast/weekly',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Dashboard Forecast
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardForecastDashboardForecastGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/forecast',
        });
    }
    /**
     * Agent Strategy Weekly
     * @returns any Successful Response
     * @throws ApiError
     */
    public static agentStrategyWeeklyAgentStrategyWeeklyPost(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/strategy/weekly',
        });
    }
    /**
     * Task Dependency Map
     * @returns any Successful Response
     * @throws ApiError
     */
    public static taskDependencyMapTaskDependencyMapPost({
        requestBody,
    }: {
        requestBody: DependencyMapRequest,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/task/dependency-map',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Mobile Task
     * @returns any Successful Response
     * @throws ApiError
     */
    public static mobileTaskMobileTaskPost({
        requestBody,
    }: {
        requestBody: MobileTask,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/mobile/task',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Recurring
     * @returns any Successful Response
     * @throws ApiError
     */
    public static getRecurringAgentRecurringGet(): CancelablePromise<Array<Record<string, any>>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/agent/recurring',
        });
    }
    /**
     * Add Recurring
     * @returns any Successful Response
     * @throws ApiError
     */
    public static addRecurringAgentRecurringAddPost({
        requestBody,
    }: {
        requestBody: RecurringTask,
    }): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/agent/recurring/add',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Dashboard Status
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardStatusDashboardStatusGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/status',
        });
    }
    /**
     * Dashboard Tasks
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardTasksDashboardTasksGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/tasks',
        });
    }
    /**
     * Dashboard Full
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardFullDashboardFullGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/full',
        });
    }
    /**
     * Dashboard Metrics
     * Return basic counts from log files.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardMetricsDashboardMetricsGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/metrics',
        });
    }
    /**
     * Dashboard Sync
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardSyncDashboardSyncGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/sync',
        });
    }
    /**
     * Dashboard Ops
     * Combined operations metrics including sales and signups.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static dashboardOpsDashboardOpsGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/dashboard/ops',
        });
    }
    /**
     * Diagnostics State
     * @returns any Successful Response
     * @throws ApiError
     */
    public static diagnosticsStateDiagnosticsStateGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/diagnostics/state',
        });
    }
    /**
     * Tana Scan
     * @returns any Successful Response
     * @throws ApiError
     */
    public static tanaScanTanaScanGet(): CancelablePromise<Record<string, any>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/tana/scan',
        });
    }
    /**
     * Metrics Endpoint
     * Prometheus metrics endpoint.
     * @returns any Successful Response
     * @throws ApiError
     */
    public static metricsEndpointMetricsGet(): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/metrics',
        });
    }
    /**
     * Health
     * Basic health check endpoint used by monitoring services.
     * @returns string Successful Response
     * @throws ApiError
     */
    public static healthHealthGet(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/health',
        });
    }
    /**
     * Protected Test
     * @returns string Successful Response
     * @throws ApiError
     */
    public static protectedTestProtectedTestPost(): CancelablePromise<Record<string, string>> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/protected-test',
        });
    }
}
