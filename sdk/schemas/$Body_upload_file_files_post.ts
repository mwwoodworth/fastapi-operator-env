/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $Body_upload_file_files_post = {
    properties: {
        uploader: {
            type: 'string',
            isRequired: true,
        },
        thread_id: {
            type: 'any-of',
            contains: [{
                type: 'number',
            }, {
                type: 'null',
            }],
        },
        task_id: {
            type: 'any-of',
            contains: [{
                type: 'number',
            }, {
                type: 'null',
            }],
        },
        metadata: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        file: {
            type: 'binary',
            isRequired: true,
            format: 'binary',
        },
    },
} as const;
