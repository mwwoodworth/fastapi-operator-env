/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type MessageCreate = {
    thread_id: number;
    sender: string;
    content: string;
    recipient?: (string | null);
    metadata?: (Record<string, any> | null);
    attachments?: (Record<string, any> | null);
};

