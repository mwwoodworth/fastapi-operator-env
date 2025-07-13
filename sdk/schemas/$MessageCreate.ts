/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $MessageCreate = {
    properties: {
        thread_id: {
            type: 'number',
            isRequired: true,
        },
        sender: {
            type: 'string',
            isRequired: true,
        },
        content: {
            type: 'string',
            isRequired: true,
        },
        recipient: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        metadata: {
            type: 'any-of',
            contains: [{
                type: 'dictionary',
                contains: {
                    properties: {
                    },
                },
            }, {
                type: 'null',
            }],
        },
        attachments: {
            type: 'any-of',
            contains: [{
                type: 'dictionary',
                contains: {
                    properties: {
                    },
                },
            }, {
                type: 'null',
            }],
        },
    },
} as const;
