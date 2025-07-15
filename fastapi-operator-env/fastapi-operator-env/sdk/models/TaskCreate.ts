/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type TaskCreate = {
    title: string;
    description?: (string | null);
    status?: string;
    assigned_to: string;
    created_by: string;
    due_date?: (string | null);
    parent_task?: (number | null);
    thread_id?: (number | null);
    priority?: (number | null);
    tags?: Array<string>;
};

