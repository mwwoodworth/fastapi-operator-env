/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $TaskRunRequest = {
    properties: {
        task: {
            type: 'string',
            isRequired: true,
        },
        context: {
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
        stream: {
            type: 'any-of',
            contains: [{
                type: 'boolean',
            }, {
                type: 'null',
            }],
        },
    },
} as const;
