/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ChatToTaskRequest = {
    properties: {
        message: {
            type: 'string',
            isRequired: true,
        },
        model: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
        memory_scope: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'number',
            }, {
                type: 'null',
            }],
        },
        session_id: {
            type: 'any-of',
            contains: [{
                type: 'string',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
